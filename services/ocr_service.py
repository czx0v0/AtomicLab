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
                    self._ocr_engine = PaddleOCR(
                        use_angle_cls=True,
                        lang='ch',  # 中英文混合
                        show_log=False,
                        use_gpu=False
                    )
                    print("✓ PaddleOCR引擎初始化成功")
                except Exception as e:
                    print(f"⚠️ PaddleOCR初始化失败: {e}")
                    self._ocr_engine = "paddle_failed"
            elif EASYOCR_AVAILABLE:
                try:
                    self._ocr_engine = easyocr.Reader(['ch_sim', 'en'], gpu=False)
                    print("✓ EasyOCR引擎初始化成功")
                except Exception as e:
                    print(f"⚠️ EasyOCR初始化失败: {e}")
                    self._ocr_engine = "easy_failed"
            else:
                print("⚠️ 未安装OCR引擎，请安装 paddleocr 或 easyocr")
                self._ocr_engine = "none"
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
                "boxes": [...]  # 文字位置框
            }
        """
        engine = self.engine
        
        if engine == "none" or engine == "paddle_failed" or engine == "easy_failed":
            return self._fallback_ocr(image_data)
        
        try:
            # 解码base64图片
            if image_data.startswith("data:image"):
                image_data = image_data.split(",", 1)[1]
            
            image_bytes = base64.b64decode(image_data)
            image = io.BytesIO(image_bytes)
            
            # 使用PaddleOCR
            if PADDLEOCR_AVAILABLE and hasattr(engine, 'ocr'):
                result = engine.ocr(image.read(), cls=True)
                
                if result and result[0]:
                    texts = []
                    boxes = []
                    total_conf = 0
                    count = 0
                    
                    for line in result[0]:
                        if len(line) >= 2:
                            box = line[0]  # 坐标
                            text_info = line[1]  # (文字, 置信度)
                            text = text_info[0] if isinstance(text_info, tuple) else str(text_info)
                            conf = text_info[1] if isinstance(text_info, tuple) and len(text_info) > 1 else 1.0
                            
                            texts.append(text)
                            boxes.append(box)
                            total_conf += conf
                            count += 1
                    
                    return {
                        "text": "\n".join(texts),
                        "confidence": total_conf / count if count > 0 else 0,
                        "boxes": boxes
                    }
            
            # 使用EasyOCR
            elif EASYOCR_AVAILABLE and hasattr(engine, 'readtext'):
                import numpy as np
                from PIL import Image
                
                img = Image.open(image)
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
                
                return {
                    "text": "\n".join(texts),
                    "confidence": total_conf / len(results) if results else 0,
                    "boxes": boxes
                }
                
        except Exception as e:
            print(f"OCR识别错误: {e}")
            return self._fallback_ocr(image_data)
        
        return {"text": "", "confidence": 0, "boxes": []}
    
    def _fallback_ocr(self, image_data: str) -> dict:
        """降级处理 - 返回提示信息"""
        return {
            "text": "[OCR服务未安装，请安装paddleocr或easyocr]",
            "confidence": 0,
            "boxes": []
        }


# 全局实例
_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """获取OCR服务实例"""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
