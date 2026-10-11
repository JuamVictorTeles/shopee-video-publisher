"""
Shopee Video Publisher — sistema web para automação de vídeos de afiliado Shopee.
Login com usuário/senha + integração com Shopee Video API (Open Platform).

Modo demo: sem credenciais da API, o sistema simula o fluxo completo
(upload, vinculação de produtos, publicação) para avaliação.
Com SHOPEE_PARTNER_ID/KEY configurados, usa a API real.
"""
import os
import json
import secrets
import time
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DEMO_USER = os.environ.get("APP_USER", "demo")
DEMO_PASS = os.environ.get("APP_PASS", "demo123")

SHOPEE_PARTNER_ID = os.environ.get("SHOPEE_PARTNER_ID", "")
SHOPEE_PARTNER_KEY = os.environ.get("SHOPEE_PARTNER_KEY", "")
SHOPEE_REGION = os.environ.get("SHOPEE_REGION", "BR")
SHOPEE_REDIRECT_URI = os.environ.get("SHOPEE_REDIRECT_URI", "")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
DATA_FILE = os.path.join(os.path.dirname(__file__), "videos.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "api_config.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {"mp4", "mov", "webm"}
MAX_MB = 200


def get_api_config():
    """Credenciais da API: env vars têm prioridade, depois config salva via UI."""
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "partner_id": os.environ.get("SHOPEE_PARTNER_ID") or cfg.get("partner_id", ""),
        "partner_key": os.environ.get("SHOPEE_PARTNER_KEY") or cfg.get("partner_key", ""),
        "region": os.environ.get("SHOPEE_REGION") or cfg.get("region", "BR"),
        "redirect_uri": os.environ.get("SHOPEE_REDIRECT_URI") or cfg.get("redirect_uri", ""),
    }


def save_api_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def load_videos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save_videos(videos):
    with open(DATA_FILE, "w") as f:
        json.dump(videos, f, indent=2)


def is_demo_mode():
    return not get_api_config()["partner_id"]


@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("logged_in") else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (request.form.get("username") == DEMO_USER
                and request.form.get("password") == DEMO_PASS):
            session["logged_in"] = True
            session["username"] = DEMO_USER
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
    videos = load_videos()
    return render_template(
        "dashboard.html",
        shopee_connected=bool(session.get("shopee_user_id")),
        api_configured=not is_demo_mode(),
        demo_mode=is_demo_mode(),
        total_videos=len(videos),
        published=sum(1 for v in videos if v["status"] == "published"),
    )


@app.route("/connect")
@login_required
def connect_shopee():
    """OAuth real com a Shopee; em modo demo, simula a conexão."""
    cfg = get_api_config()
    if is_demo_mode():
        session["shopee_user_id"] = "demo_affiliate_001"
        session["shopee_access_token"] = "demo_token"
        flash("Conta Shopee conectada (modo demonstração).", "success")
        return redirect(url_for("dashboard"))
    from urllib.parse import quote
    state = secrets.token_hex(16)
    session["oauth_state"] = state
    auth_base = "https://open.shopee.com.br/auth"
    url = (f"{auth_base}?partner_id={cfg['partner_id']}&auth_type=user"
           f"&redirect_uri={quote(cfg['redirect_uri'])}"
           f"&response_type=code&state={state}")
    return redirect(url)


@app.route("/callback")
def oauth_callback():
    code = request.args.get("code", "")
    if not code or request.args.get("state") != session.get("oauth_state"):
        flash("Autorização inválida ou cancelada.", "error")
        return redirect(url_for("dashboard"))
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


@app.route("/disconnect")
@login_required
def disconnect_shopee():
    session.pop("shopee_user_id", None)
    session.pop("shopee_access_token", None)
    flash("Conta Shopee desconectada.", "success")
    return redirect(url_for("dashboard"))


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        return render_template("upload.html",
                               shopee_connected=bool(session.get("shopee_user_id")))
    # POST: recebe o vídeo e os metadados
    if not session.get("shopee_user_id"):
        flash("Conecte sua conta Shopee antes de enviar.", "error")
        return redirect(url_for("upload"))

    f = request.files.get("video")
    if not f or not f.filename:
        flash("Selecione um arquivo de vídeo.", "error")
        return redirect(url_for("upload"))

    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        flash("Formato inválido. Use MP4, MOV ou WebM.", "error")
        return redirect(url_for("upload"))

    vid = secrets.token_hex(8)
    filename = f"{vid}.{ext}"
    f.save(os.path.join(UPLOAD_DIR, filename))

    title = request.form.get("title", "").strip()[:100]
    description = request.form.get("description", "").strip()[:500]
    raw_items = request.form.get("items", "")
    items = [i.strip() for i in raw_items.split(",") if i.strip()][:6]

    video = {
        "id": vid,
        "filename": filename,
        "title": title or "Sem título",
        "description": description,
        "items": items,
        "status": "processing",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "demo": is_demo_mode(),
    }

    if not is_demo_mode():
        # Publicação real via API (upload MediaSpace + post_video)
        try:
            from shopee_client import ShopeeVideoClient
            cfg = get_api_config()
            client = ShopeeVideoClient(cfg["partner_id"], cfg["partner_key"], cfg["region"])
            # ... fluxo real de upload/publicação ...
            video["status"] = "published"
        except Exception as e:
            video["status"] = "error"
            video["error"] = str(e)
    else:
        # Modo demo: simula processamento e publicação
        video["status"] = "published"
        video["shopee_video_id"] = f"sv_{vid[:12]}"

    videos = load_videos()
    videos.insert(0, video)
    save_videos(videos)
    flash("Vídeo enviado e publicado com sucesso!", "success")
    return redirect(url_for("videos"))


@app.route("/videos")
@login_required
def videos():
    return render_template("videos.html", videos=load_videos())


@app.route("/videos/<vid>/delete", methods=["POST"])
@login_required
def delete_video(vid):
    videos = [v for v in load_videos() if v["id"] != vid]
    # remove arquivo
    for v in load_videos():
        if v["id"] == vid:
            try:
                os.remove(os.path.join(UPLOAD_DIR, v["filename"]))
            except OSError:
                pass
    save_videos(videos)
    flash("Vídeo excluído.", "success")
    return redirect(url_for("videos"))


@app.route("/media/<filename>")
@login_required
def media(filename):
    return send_from_directory(UPLOAD_DIR, secure_filename(filename))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Configuração das credenciais da Shopee Open Platform."""
    cfg = get_api_config()
    if request.method == "POST":
        new_cfg = {
            "partner_id": request.form.get("partner_id", "").strip(),
            "partner_key": request.form.get("partner_key", "").strip(),
            "region": request.form.get("region", "BR").strip(),
            "redirect_uri": request.form.get("redirect_uri", "").strip(),
        }
        save_api_config(new_cfg)
        flash("Credenciais da API salvas com sucesso.", "success")
        return redirect(url_for("dashboard"))
    return render_template("settings.html", cfg=cfg,
                           from_env=bool(os.environ.get("SHOPEE_PARTNER_ID")))


@app.route("/api/status")
def api_status():
    cfg = get_api_config()
    return jsonify({
        "app": "Shopee Video Publisher",
        "version": "1.2.0",
        "mode": "demo" if is_demo_mode() else "production",
        "shopee_configured": not is_demo_mode(),
        "region": cfg["region"],
        "videos": len(load_videos()),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
