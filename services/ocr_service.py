"""
OCR Service
===========
截图文字识别服务 - 使用VLM视觉语言模型

使用ModelScope API调用Qwen2-VL等视觉模型，无需本地OCR依赖。
"""

import base64
import traceback
from typing import Optional
from openai import OpenAI

from core.config import API_BASE, MS_KEY

# VLM模型配置
VLM_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"  # 可替换为其他视觉模型


class OCRService:
    """OCR识别服务 - 使用VLM视觉语言模型"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def recognize(self, image_data: str) -> dict:
        """
        使用VLM识别图片中的文字

        Args:
            image_data: base64编码的图片数据

        Returns:
            dict: {
                "text": "识别的文字",
                "confidence": 0.95,
                "engine": "vlm"
            }
        """
        if not MS_KEY:
            return {
                "text": "",
                "confidence": 0,
                "error": "未配置API Key (MS_KEY)",
            }

        try:
            # 处理base64图片数据
            if image_data.startswith("data:image"):
                image_base64 = image_data.split(",", 1)[1]
            else:
                image_base64 = image_data

            # 验证图片数据
            image_bytes = base64.b64decode(image_base64)
            if len(image_bytes) < 100:
                return {
                    "text": "",
                    "confidence": 0,
                    "error": "图片数据过小",
                }

            print(f"[VLM] 使用 {VLM_MODEL} 识别图片 ({len(image_bytes)} bytes)...")

            # 构建图片URL (data URI格式)
            image_url = f"data:image/png;base64,{image_base64}"

            # 调用VLM API
            client = OpenAI(base_url=API_BASE, api_key=MS_KEY, max_retries=1)

            response = client.chat.completions.create(
                model=VLM_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "请识别并提取图片中的所有文字内容。如果有公式，请用LaTeX格式输出。只输出识别的文字，不要添加任何解释。"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url}
                            }
                        ]
                    }
                ],
                max_tokens=2000,
            )

            recognized_text = response.choices[0].message.content
            
            if recognized_text:
                print(f"[VLM] 识别成功: {len(recognized_text)} 字符")
                return {
                    "text": recognized_text,
                    "confidence": 0.9,  # VLM通常置信度高
                    "engine": "vlm",
                    "model": VLM_MODEL,
                }
            else:
                print("[VLM] 未识别到文字")
                return {
                    "text": "",
                    "confidence": 0,
                    "engine": "vlm",
                }

        except Exception as e:
            error_msg = str(e)
            print(f"[VLM] 识别错误: {error_msg}")
            print(f"[VLM] 错误堆栈: {traceback.format_exc()}")
            return {
                "text": "",
                "confidence": 0,
                "error": error_msg,
            }

    def is_available(self) -> bool:
        """检查OCR服务是否可用"""
        return bool(MS_KEY)


# 全局实例
_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """获取OCR服务实例"""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
