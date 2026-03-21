"""
OCR Service
===========
截图文字识别服务

支持多种OCR引擎:
- PaddleOCR (推荐，免费本地运行)
- EasyOCR (备选)
- 百度OCR API (需API Key)
"""

import base64
import io
import traceback
from typing import Optional


# 尝试导入PaddleOCR
try:
    from paddleocr import PaddleOCR

    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False

# 尝试导入EasyOCR
try:
    import easyocr

    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


class OCRService:
    """OCR识别服务"""

    _instance = None
    _ocr_engine = None
    _engine_type = None  # 'paddle', 'easy', 'none'

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def engine(self):
        """延迟加载OCR引擎"""
        if self._ocr_engine is None:
            if PADDLEOCR_AVAILABLE:
                try:
                    print("[OCR] 正在初始化 PaddleOCR 引擎...")
                    self._ocr_engine = PaddleOCR(
                        use_angle_cls=True,
                        lang="ch",  # 中英文混合
                        show_log=False,
                        use_gpu=False,
                    )
                    self._engine_type = "paddle"
                    print("[OCR] ✓ PaddleOCR引擎初始化成功")
                except Exception as e:
                    print(f"[OCR] ⚠️ PaddleOCR初始化失败: {e}")
                    print(f"[OCR] 错误详情: {traceback.format_exc()}")
                    self._ocr_engine = None
            elif EASYOCR_AVAILABLE:
                try:
                    print("[OCR] 正在初始化 EasyOCR 引擎...")
                    self._ocr_engine = easyocr.Reader(["ch_sim", "en"], gpu=False)
                    self._engine_type = "easy"
                    print("[OCR] ✓ EasyOCR引擎初始化成功")
                except Exception as e:
                    print(f"[OCR] ⚠️ EasyOCR初始化失败: {e}")
                    print(f"[OCR] 错误详情: {traceback.format_exc()}")
                    self._ocr_engine = None
            else:
                print("[OCR] ⚠️ 未安装OCR引擎，请安装 paddleocr 或 easyocr")
                self._ocr_engine = None
                self._engine_type = "none"
        return self._ocr_engine

    def recognize(self, image_data: str) -> dict:
        """
        识别图片中的文字

        Args:
            image_data: base64编码的图片数据

        Returns:
            dict: {
                "text": "识别的文字",
                "confidence": 0.95,
                "boxes": [...],  # 文字位置框
                "engine": "paddle"  # 使用的引擎
            }
        """
        engine = self.engine

        if engine is None:
            return self._fallback_ocr(image_data, "OCR引擎未初始化")

        try:
            # 解码base64图片
            if image_data.startswith("data:image"):
                image_data = image_data.split(",", 1)[1]

            image_bytes = base64.b64decode(image_data)

            # 验证图片数据
            if len(image_bytes) < 100:
                print(f"[OCR] 图片数据过小: {len(image_bytes)} bytes")
                return {
                    "text": "",
                    "confidence": 0,
                    "boxes": [],
                    "error": "图片数据过小",
                }

            image = io.BytesIO(image_bytes)

            # 使用PaddleOCR
            if self._engine_type == "paddle" and hasattr(engine, "ocr"):
                print(f"[OCR] 使用PaddleOCR识别图片 ({len(image_bytes)} bytes)...")

                try:
                    result = engine.ocr(image.read(), cls=True)
                except Exception as ocr_error:
                    # 尝试使用PIL转换后再识别
                    print(f"[OCR] 直接识别失败，尝试转换图片格式: {ocr_error}")
                    try:
                        from PIL import Image
                        import numpy as np

                        image.seek(0)
                        img = Image.open(image)
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                        img_array = np.array(img)
                        result = engine.ocr(img_array, cls=True)
                    except Exception as conv_error:
                        print(f"[OCR] 图片转换失败: {conv_error}")
                        return self._fallback_ocr(image_data, str(conv_error))

                if result and result[0]:
                    texts = []
                    boxes = []
                    total_conf = 0
                    count = 0

                    for line in result[0]:
                        if len(line) >= 2:
                            box = line[0]  # 坐标
                            text_info = line[1]  # (文字, 置信度)
                            text = (
                                text_info[0]
                                if isinstance(text_info, tuple)
                                else str(text_info)
                            )
                            conf = (
                                text_info[1]
                                if isinstance(text_info, tuple) and len(text_info) > 1
                                else 1.0
                            )

                            texts.append(text)
                            boxes.append(box)
                            total_conf += conf
                            count += 1

                    if texts:
                        recognized_text = "\n".join(texts)
                        print(
                            f"[OCR] 识别成功: {len(texts)} 行文字, 平均置信度 {total_conf/count:.2f}"
                        )
                        return {
                            "text": recognized_text,
                            "confidence": total_conf / count if count > 0 else 0,
                            "boxes": boxes,
                            "engine": "paddle",
                        }

            # 使用EasyOCR
            elif self._engine_type == "easy" and hasattr(engine, "readtext"):
                print(f"[OCR] 使用EasyOCR识别图片 ({len(image_bytes)} bytes)...")
                import numpy as np
                from PIL import Image

                image.seek(0)
                img = Image.open(image)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img_array = np.array(img)

                results = engine.readtext(img_array)

                texts = []
                boxes = []
                total_conf = 0

                for detection in results:
                    box, text, conf = detection
                    texts.append(text)
                    boxes.append(box)
                    total_conf += conf

                if texts:
                    print(f"[OCR] 识别成功: {len(texts)} 行文字")
                    return {
                        "text": "\n".join(texts),
                        "confidence": total_conf / len(results) if results else 0,
                        "boxes": boxes,
                        "engine": "easy",
                    }

            print("[OCR] 未识别到文字")
            return {
                "text": "",
                "confidence": 0,
                "boxes": [],
                "engine": self._engine_type,
            }

        except Exception as e:
            print(f"[OCR] 识别错误: {e}")
            print(f"[OCR] 错误堆栈: {traceback.format_exc()}")
            return self._fallback_ocr(image_data, str(e))

    def _fallback_ocr(self, image_data: str, error_msg: str = "") -> dict:
        """降级处理 - 返回提示信息"""
        return {
            "text": f"[OCR识别失败: {error_msg}]",
            "confidence": 0,
            "boxes": [],
            "error": error_msg,
        }

    def is_available(self) -> bool:
        """检查OCR服务是否可用"""
        return self.engine is not None and self._engine_type in ("paddle", "easy")


# 全局实例
_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """获取OCR服务实例"""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
