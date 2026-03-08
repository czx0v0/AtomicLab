"""
OCR Service
===========
截图文字识别服务

支持多种OCR引擎:
1. VLM API (需要支持的API服务)
2. EasyOCR (本地运行，免费)
3. 百度OCR API (需要API Key)

注意: ModelScope API不支持VLM模型，需要使用其他服务或本地模型
"""

import base64
import traceback
from typing import Optional

# 尝试导入EasyOCR作为备选
try:
    import easyocr

    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("[OCR] EasyOCR未安装，请运行: pip install easyocr")

from core.config import API_BASE, MS_KEY

# VLM模型配置
VLM_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"
VLM_AVAILABLE = False
VLM_ERROR = ""

# 检测VLM可用性
if MS_KEY:
    try:
        from openai import OpenAI

        client = OpenAI(base_url=API_BASE, api_key=MS_KEY, max_retries=0)
        # 尝试简单请求检测模型
        # 注意: ModelScope当前不支持VLM模型
        VLM_AVAILABLE = False  # 暂时禁用VLM
        VLM_ERROR = "ModelScope API不支持VLM模型，请使用EasyOCR"
    except Exception as e:
        VLM_ERROR = str(e)
        print(f"[OCR] VLM不可用: {e}")


class OCRService:
    """OCR识别服务 - 支持VLM和EasyOCR"""

    _instance = None
    _easyocr_reader = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def easyocr_reader(self):
        """延迟加载EasyOCR"""
        if self._easyocr_reader is None and EASYOCR_AVAILABLE:
            try:
                print("[OCR] 正在初始化EasyOCR...")
                self._easyocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
                print("[OCR] EasyOCR初始化成功")
            except Exception as e:
                print(f"[OCR] EasyOCR初始化失败: {e}")
        return self._easyocr_reader

    def recognize(self, image_data: str) -> dict:
        """
        识别图片中的文字

        Args:
            image_data: base64编码的图片数据

        Returns:
            dict: {
                "text": "识别的文字",
                "confidence": 0.95,
                "engine": "easyocr"
            }
        """
        # 优先使用EasyOCR（因为VLM不可用）
        if self.easyocr_reader:
            return self._recognize_easyocr(image_data)

        # 如果EasyOCR不可用，返回错误
        return {
            "text": "",
            "confidence": 0,
            "error": "OCR不可用：请安装EasyOCR (pip install easyocr) 或配置支持VLM的API服务",
        }

    def _recognize_easyocr(self, image_data: str) -> dict:
        """使用EasyOCR识别"""
        try:
            # 处理base64图片数据
            if image_data.startswith("data:image"):
                image_base64 = image_data.split(",", 1)[1]
            else:
                image_base64 = image_data

            # 解码图片
            import numpy as np
            from PIL import Image
            import io

            image_bytes = base64.b64decode(image_base64)
            if len(image_bytes) < 100:
                return {
                    "text": "",
                    "confidence": 0,
                    "error": "图片数据过小",
                }

            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != "RGB":
                image = image.convert("RGB")
            img_array = np.array(image)

            print(f"[EasyOCR] 识别图片 ({len(image_bytes)} bytes)...")
            results = self.easyocr_reader.readtext(img_array)

            texts = []
            total_conf = 0
            for detection in results:
                box, text, conf = detection
                texts.append(text)
                total_conf += conf

            if texts:
                recognized_text = "\n".join(texts)
                avg_conf = total_conf / len(results) if results else 0
                print(f"[EasyOCR] 识别成功: {len(texts)} 行文字, 置信度 {avg_conf:.2f}")
                return {
                    "text": recognized_text,
                    "confidence": avg_conf,
                    "engine": "easyocr",
                }
            else:
                print("[EasyOCR] 未识别到文字")
                return {
                    "text": "",
                    "confidence": 0,
                    "engine": "easyocr",
                }

        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            print(f"[EasyOCR] 识别错误 ({error_type}): {error_msg}")
            print(f"[EasyOCR] 错误堆栈: {traceback.format_exc()}")
            return {
                "text": "",
                "confidence": 0,
                "error": f"{error_type}: {error_msg}",
            }

    def is_available(self) -> bool:
        """检查OCR服务是否可用"""
        return self.easyocr_reader is not None


# 全局实例
_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """获取OCR服务实例"""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
