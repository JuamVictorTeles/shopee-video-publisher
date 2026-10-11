"""
Shopee Video Publisher — sistema web para automação de vídeos de afiliado Shopee.
Login com usuário/senha + integração com Shopee Video API (Open Platform).
"""
import os
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Usuário demo para avaliação da Shopee
DEMO_USER = os.environ.get("APP_USER", "demo")
DEMO_PASS = os.environ.get("APP_PASS", "demo123")

# Config Shopee Open Platform (preenchido após aprovação do app)
SHOPEE_PARTNER_ID = os.environ.get("SHOPEE_PARTNER_ID", "")
SHOPEE_PARTNER_KEY = os.environ.get("SHOPEE_PARTNER_KEY", "")
SHOPEE_REGION = os.environ.get("SHOPEE_REGION", "BR")
SHOPEE_REDIRECT_URI = os.environ.get("SHOPEE_REDIRECT_URI", "")

# Base URLs por região
SHOPEE_AUTH_URLS = {
    "BR": "https://open.shopee.com.br/auth",
    "GLOBAL": "https://open.shopee.com/auth",
}
SHOPEE_API_URLS = {
    "BR": "https://openplatform.shopee.com.br/api/v2",
    "GLOBAL": "https://partner.shopeemobile.com/api/v2",
}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def index():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username", "")
        pwd = request.form.get("password", "")
        if user == DEMO_USER and pwd == DEMO_PASS:
            session["logged_in"] = True
            session["username"] = user
            return redirect(url_for("dashboard"))
        flash("Usuário ou senha inválidos.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    shopee_connected = bool(session.get("shopee_user_id"))
    return render_template("dashboard.html",
                           shopee_connected=shopee_connected,
                           api_configured=bool(SHOPEE_PARTNER_ID))


@app.route("/connect")
@login_required
def connect_shopee():
    """Inicia o OAuth com a Shopee (affiliate = auth_type=user)."""
    if not SHOPEE_PARTNER_ID:
        flash("Credenciais da Shopee ainda não configuradas.", "error")
        return redirect(url_for("dashboard"))
    auth_base = SHOPEE_AUTH_URLS.get(SHOPEE_REGION, SHOPEE_AUTH_URLS["GLOBAL"])
    state = secrets.token_hex(16)
    session["oauth_state"] = state
    url = (f"{auth_base}?partner_id={SHOPEE_PARTNER_ID}"
           f"&auth_type=user&redirect_uri={SHOPEE_REDIRECT_URI}"
           f"&response_type=code&state={state}")
    return redirect(url)


@app.route("/callback")
def oauth_callback():
    """Recebe o code da Shopee após autorização."""
    code = request.args.get("code", "")
    state = request.args.get("state", "")
    if not code or state != session.get("oauth_state"):
        flash("Autorização inválida ou cancelada.", "error")
        return redirect(url_for("dashboard"))
    # Troca o code por access_token (implementado em shopee_client.py)
    from shopee_client import exchange_code
    try:
        data = exchange_code(code)
        session["shopee_user_id"] = data.get("user_id")
        session["shopee_access_token"] = data.get("access_token")
        session["shopee_refresh_token"] = data.get("refresh_token")
        flash("Conta Shopee conectada com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao conectar: {e}", "error")
    return redirect(url_for("dashboard"))


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        # Upload do vídeo + metadados; publicação via API
        return jsonify({"status": "received"})
    return render_template("upload.html")


@app.route("/videos")
@login_required
def videos():
    return render_template("videos.html", videos=[])


@app.route("/api/status")
def api_status():
    return jsonify({
        "app": "Shopee Video Publisher",
        "version": "1.0.0",
        "shopee_configured": bool(SHOPEE_PARTNER_ID),
        "region": SHOPEE_REGION,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
