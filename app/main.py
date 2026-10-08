import logging

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import BackgroundTasks, Depends, FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.database import Base, engine, get_db
from app.emailer import money, send_order_confirmation
from app.models import Order, OrderItem, Product, User
from app.seed import seed_products

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Bootcamp Shop")
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    https_only=config.BASE_URL.startswith("https"),
    same_site="lax",
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.filters["money"] = money

oauth = OAuth()
oauth.register(
    name="google",
    client_id=config.GOOGLE_CLIENT_ID,
    client_secret=config.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)  # creates the tables in Supabase/Neon
    seed_products()


# ---------- helpers ----------

def current_user(request: Request, db: Session) -> User | None:
    uid = request.session.get("user_id")
    return db.get(User, uid) if uid else None


def get_cart(request: Request) -> dict[str, int]:
    return request.session.setdefault("cart", {})


def cart_lines(request: Request, db: Session):
    lines, total = [], 0
    for pid, qty in list(get_cart(request).items()):
        product = db.get(Product, int(pid))
        if product is None:
            continue
        subtotal = product.price_cents * qty
        total += subtotal
        lines.append({"product": product, "qty": qty, "subtotal": subtotal})
    return lines, total


def render(request: Request, db: Session, name: str, **ctx):
    cart_count = sum(get_cart(request).values())
    return templates.TemplateResponse(
        request,
        name,
        {"user": current_user(request, db), "cart_count": cart_count, **ctx},
    )


# ---------- PWA ----------

@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # Must be served from the site root so it can control every page.
    return FileResponse(
        "static/sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@app.get("/manifest.webmanifest", include_in_schema=False)
def web_manifest():
    return FileResponse(
        "static/manifest.webmanifest",
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/.well-known/assetlinks.json", include_in_schema=False)
def asset_links():
    # Proves the Android app (Trusted Web Activity) belongs to this site,
    # which removes the Chrome address bar inside the APK.
    return JSONResponse(
        [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": "com.Tboiii.bootcampshop",
                    "sha256_cert_fingerprints": [
                        "C5:D7:6B:D3:28:E9:CE:85:F3:D5:3C:EB:79:9F:1E:79:9D:B2:FD:43:88:33:14:B8:E7:BE:61:4F:42:CE:EC:50"
                    ],
                },
            }
        ]
    )


@app.get("/offline", include_in_schema=False)
def offline_page(request: Request, db: Session = Depends(get_db)):
    return render(request, db, "offline.html")


# ---------- shop ----------

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.id).all()
    return render(request, db, "index.html", products=products)


@app.post("/cart/add/{product_id}")
def cart_add(product_id: int, request: Request, db: Session = Depends(get_db)):
    if db.get(Product, product_id):
        cart = get_cart(request)
        cart[str(product_id)] = cart.get(str(product_id), 0) + 1
        request.session["cart"] = cart
    return RedirectResponse(request.headers.get("referer", "/"), status_code=303)


@app.post("/cart/update/{product_id}")
def cart_update(product_id: int, request: Request, delta: int = Form(...)):
    cart = get_cart(request)
    new_qty = cart.get(str(product_id), 0) + delta
    if new_qty <= 0:
        cart.pop(str(product_id), None)
    else:
        cart[str(product_id)] = min(new_qty, 99)
    request.session["cart"] = cart
    return RedirectResponse("/cart", status_code=303)


@app.get("/cart")
def cart_page(request: Request, db: Session = Depends(get_db)):
    lines, total = cart_lines(request, db)
    return render(request, db, "cart.html", lines=lines, total=total)


# ---------- checkout ----------

@app.get("/checkout")
def checkout_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        request.session["next"] = "/checkout"
        return RedirectResponse("/login", status_code=303)
    lines, total = cart_lines(request, db)
    if not lines:
        return RedirectResponse("/cart", status_code=303)
    return render(request, db, "checkout.html", lines=lines, total=total)


@app.post("/checkout")
def checkout_submit(
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    phone: str = Form(""),
    address: str = Form(...),
    city: str = Form(...),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lines, total = cart_lines(request, db)
    if not lines:
        return RedirectResponse("/cart", status_code=303)

    order = Order(
        user_id=user.id,
        full_name=full_name.strip(),
        email=user.email,
        phone=phone.strip(),
        address=address.strip(),
        city=city.strip(),
        total_cents=total,
        status="confirmed",
    )
    for line in lines:
        order.items.append(
            OrderItem(
                product_id=line["product"].id,
                name=line["product"].name,
                unit_price_cents=line["product"].price_cents,
                quantity=line["qty"],
            )
        )
    db.add(order)
    db.commit()  # order is saved to the database here

    request.session["cart"] = {}
    background.add_task(send_order_confirmation, order.id)
    return RedirectResponse(f"/orders/{order.id}?placed=1", status_code=303)


# ---------- orders ----------

@app.get("/orders")
def orders_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        request.session["next"] = "/orders"
        return RedirectResponse("/login", status_code=303)
    orders = (
        db.query(Order).filter(Order.user_id == user.id).order_by(Order.id.desc()).all()
    )
    return render(request, db, "orders.html", orders=orders)


@app.get("/orders/{order_id}")
def order_detail(order_id: int, request: Request, placed: int = 0, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    order = db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        return RedirectResponse("/orders", status_code=303)
    return render(request, db, "order_detail.html", order=order, placed=bool(placed))


# ---------- Google auth ----------

@app.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    configured = bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)
    return render(request, db, "login.html", configured=configured, error=request.query_params.get("error"))


@app.get("/auth/google")
async def auth_google(request: Request):
    redirect_uri = f"{config.BASE_URL}/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse("/login?error=1", status_code=303)

    info = token.get("userinfo") or {}
    sub, email = info.get("sub"), info.get("email")
    if not sub or not email:
        return RedirectResponse("/login?error=1", status_code=303)

    user = db.query(User).filter(User.google_sub == sub).first()
    if user is None:
        user = User(google_sub=sub, email=email)
        db.add(user)
    user.email = email
    user.name = info.get("name", "")
    user.picture = info.get("picture", "")
    db.commit()

    request.session["user_id"] = user.id
    return RedirectResponse(request.session.pop("next", "/"), status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    return RedirectResponse("/", status_code=303)