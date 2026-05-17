import requests
import json
import time
import os
from datetime import datetime
from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO, KIS_ACCOUNT_PROD_CD, KIS_IS_REAL

TOKEN_CACHE_PATH = os.path.join("logs", ".kis_token.json")


class KISClient:
    def __init__(self):
        self.base_url = "https://openapi.koreainvestment.com:9443" if KIS_IS_REAL else "https://openapivts.koreainvestment.com:29443"
        self.app_key = KIS_APP_KEY
        self.app_secret = KIS_APP_SECRET
        self.account_no = KIS_ACCOUNT_NO
        self.account_prod_cd = KIS_ACCOUNT_PROD_CD
        self._access_token = None
        self._token_expires = 0
        self._load_token_cache()

    def _load_token_cache(self):
        try:
            if os.path.exists(TOKEN_CACHE_PATH):
                with open(TOKEN_CACHE_PATH) as f:
                    c = json.load(f)
                if c.get("env") == ("real" if KIS_IS_REAL else "vts") and c.get("expires", 0) > time.time() + 60:
                    self._access_token = c["token"]
                    self._token_expires = c["expires"]
        except Exception:
            pass

    def _save_token_cache(self):
        try:
            os.makedirs(os.path.dirname(TOKEN_CACHE_PATH), exist_ok=True)
            with open(TOKEN_CACHE_PATH, "w") as f:
                json.dump({
                    "env": "real" if KIS_IS_REAL else "vts",
                    "token": self._access_token,
                    "expires": self._token_expires,
                }, f)
        except Exception:
            pass

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        res = requests.post(url, headers=headers, data=json.dumps(body))
        data = res.json()
        if "access_token" not in data:
            raise RuntimeError(f"KIS 토큰 발급 실패: {data}")
        self._access_token = data["access_token"]
        self._token_expires = time.time() + int(data["expires_in"]) - 60
        self._save_token_cache()
        return self._access_token

    def _headers(self, tr_id: str, extra: dict = None) -> dict:
        h = {
            "content-type": "application/json",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }
        if extra:
            h.update(extra)
        return h

    def get_current_price(self, stock_code: str) -> dict:
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code}
        res = requests.get(url, headers=self._headers("FHKST01010100"), params=params)
        data = res.json()
        output = data.get("output", {})
        return {
            "code": stock_code,
            "price": int(output.get("stck_prpr", 0)),
            "change_rate": float(output.get("prdy_ctrt", 0)),
            "volume": int(output.get("acml_vol", 0)),
        }

    def get_intraday_minute(self, stock_code: str, hhmmss: str = "153000") -> list:
        """당일 분봉 조회. hhmmss 이전 30개 분봉 반환.
        응답 each: stck_cntg_hour(HHMMSS), stck_prpr(현재가), stck_oprc/hgpr/lwpr, cntg_vol
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        params = {
            "FID_ETC_CLS_CODE": "",
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_HOUR_1": hhmmss,
            "FID_PW_DATA_INCU_YN": "N",
        }
        res = requests.get(url, headers=self._headers("FHKST03010200"), params=params)
        return res.json().get("output2", [])

    def get_ohlcv(self, stock_code: str, period: str = "D", count: int = 100) -> list:
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        today = datetime.today().strftime("%Y%m%d")
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_DATE_1": "20240101",
            "FID_INPUT_DATE_2": today,
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0",
        }
        res = requests.get(url, headers=self._headers("FHKST03010100"), params=params)
        return res.json().get("output2", [])

    def get_balance(self) -> dict:
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        params = {
            "CANO": self.account_no[:8],
            "ACNT_PRDT_CD": self.account_prod_cd,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        tr_id = "TTTC8434R" if KIS_IS_REAL else "VTTC8434R"
        res = requests.get(url, headers=self._headers(tr_id), params=params)
        return res.json()

    def buy_order(self, stock_code: str, qty: int, price: int = 0, order_type: str = "01"):
        """order_type: 00=지정가, 01=시장가"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        tr_id = "TTTC0802U" if KIS_IS_REAL else "VTTC0802U"
        body = {
            "CANO": self.account_no[:8],
            "ACNT_PRDT_CD": self.account_prod_cd,
            "PDNO": stock_code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price),
        }
        res = requests.post(url, headers=self._headers(tr_id, {"hashkey": self._get_hashkey(body)}), data=json.dumps(body))
        return res.json()

    def sell_order(self, stock_code: str, qty: int, price: int = 0, order_type: str = "01"):
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        tr_id = "TTTC0801U" if KIS_IS_REAL else "VTTC0801U"
        body = {
            "CANO": self.account_no[:8],
            "ACNT_PRDT_CD": self.account_prod_cd,
            "PDNO": stock_code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price),
        }
        res = requests.post(url, headers=self._headers(tr_id, {"hashkey": self._get_hashkey(body)}), data=json.dumps(body))
        return res.json()

    def _get_hashkey(self, body: dict) -> str:
        url = f"{self.base_url}/uapi/hashkey"
        headers = {
            "content-type": "application/json",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        res = requests.post(url, headers=headers, data=json.dumps(body))
        return res.json().get("HASH", "")
