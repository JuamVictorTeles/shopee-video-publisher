"""
Cliente da Shopee Video API (Open Platform v2).
Cobre: OAuth (affiliate), upload de vídeo (MediaSpace) e publicação (v2.video.*).
Baseado no Shopee Video API Integration Guide (developer-guide/706).
"""
import time
import hmac
import hashlib
import requests

SHOPEE_API_URLS = {
    "BR": "https://openplatform.shopee.com.br/api/v2",
    "GLOBAL": "https://partner.shopeemobile.com/api/v2",
}
SHOPEE_AUTH_URLS = {
    "BR": "https://open.shopee.com.br",
    "GLOBAL": "https://open.shopee.com",
}


class ShopeeVideoClient:
    def __init__(self, partner_id, partner_key, region="BR"):
        self.partner_id = int(partner_id)
        self.partner_key = partner_key
        self.region = region
        self.api_base = SHOPEE_API_URLS.get(region, SHOPEE_API_URLS["GLOBAL"])
        self.auth_base = SHOPEE_AUTH_URLS.get(region, SHOPEE_AUTH_URLS["GLOBAL"])

    def _sign(self, api_path, timestamp, access_token="", user_id=""):
        """Assinatura HMAC-SHA256 (User-type API: inclui user_id)."""
        base = f"{self.partner_id}{api_path}{timestamp}{access_token}{user_id}"
        return hmac.new(
            self.partner_key.encode(), base.encode(), hashlib.sha256
        ).hexdigest()

    def _call(self, api_path, body=None, user_id="", access_token=""):
        ts = int(time.time())
        sign = self._sign(api_path, ts, access_token, user_id)
        params = {
            "partner_id": self.partner_id,
            "timestamp": ts,
            "sign": sign,
        }
        if access_token:
            params["access_token"] = access_token
        if user_id:
            params["user_id"] = user_id
        r = requests.post(f"{self.api_base}{api_path}",
                          params=params, json=body or {}, timeout=60)
        r.raise_for_status()
        return r.json()

    # ---- OAuth ----
    def exchange_code(self, code):
        return self._call("/public/get_access_token", {"code": code,
                          "partner_id": self.partner_id})

    def refresh_token(self, refresh_token, user_id):
        return self._call("/public/refresh_access_token",
                          {"refresh_token": refresh_token,
                           "partner_id": self.partner_id},
                          user_id=user_id)

    # ---- MediaSpace: upload de vídeo ----
    def init_video_upload(self, file_md5, file_size, user_id, access_token):
        return self._call("/media_space/init_video_upload",
                          {"file_md5": file_md5, "file_size": file_size},
                          user_id, access_token)

    def upload_video_part(self, upload_id, part_number, file_data,
                          user_id, access_token):
        ts = int(time.time())
        api_path = "/media_space/upload_video_part"
        sign = self._sign(api_path, ts, access_token, user_id)
        params = {"partner_id": self.partner_id, "timestamp": ts,
                  "sign": sign, "access_token": access_token,
                  "user_id": user_id}
        files = {"file_data": ("part.mp4", file_data, "video/mp4")}
        data = {"upload_id": upload_id, "part_number": part_number}
        r = requests.post(f"{self.api_base}{api_path}", params=params,
                          data=data, files=files, timeout=120)
        r.raise_for_status()
        return r.json()

    def complete_video_upload(self, upload_id, part_list, user_id, access_token):
        return self._call("/media_space/complete_video_upload",
                          {"upload_id": upload_id,
                           "part_seq_list": part_list},
                          user_id, access_token)

    def get_video_upload_result(self, upload_id, user_id, access_token):
        return self._call("/media_space/get_video_upload_result",
                          {"upload_id": upload_id}, user_id, access_token)

    # ---- v2.video: gerenciamento e publicação ----
    def edit_video_info(self, video_id, title, description, item_list,
                        cover_url, user_id, access_token):
        return self._call("/video/edit_video_info",
                          {"video_id": video_id, "title": title,
                           "description": description,
                           "item_list": item_list, "cover_url": cover_url},
                          user_id, access_token)

    def post_video(self, video_id, user_id, access_token):
        return self._call("/video/post_video", {"video_id": video_id},
                          user_id, access_token)

    def get_video_list(self, user_id, access_token, page=1, page_size=20):
        return self._call("/video/get_video_list",
                          {"page_no": page, "page_size": page_size},
                          user_id, access_token)


def exchange_code(code):
    """Helper usado pelo callback OAuth do app.py."""
    import os, json
    cfg = {}
    cfg_path = os.path.join(os.path.dirname(__file__), "api_config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            cfg = json.load(f)
    client = ShopeeVideoClient(
        os.environ.get("SHOPEE_PARTNER_ID") or cfg.get("partner_id", ""),
        os.environ.get("SHOPEE_PARTNER_KEY") or cfg.get("partner_key", ""),
        os.environ.get("SHOPEE_REGION") or cfg.get("region", "BR"),
    )
    return client.exchange_code(code)
