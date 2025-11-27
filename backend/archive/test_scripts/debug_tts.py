#!/usr/bin/env python3
"""
Debug TTS API
"""

import asyncio
import os
import sys
import django
from pathlib import Path

# Django 설정
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from gemini.services.service_manager import get_gemini_service


async def debug_tts():
    print("[DEBUG] TTS 디버깅 시작...")

    try:
        service = get_gemini_service()
        print("[DEBUG] 서비스 매니저 로드됨")

        print("[DEBUG] 클라이언트 설정:")
        print(f"   - 모델: {service.client.config.model}")

        # 간단한 텍스트 테스트
        test_message = "Hello world"
        print(f"[DEBUG] 테스트 메시지: {test_message}")

        print("[DEBUG] process_text_with_audio 호출 중...")
        result = await service.process_text_with_audio(
            message=test_message,
            voice_name="Aoede"
        )

        print("[DEBUG] 결과:")
        for key, value in result.items():
            if key == 'audio' and value:
                print(f"   - {key}: <{len(value)} bytes>")
            else:
                print(f"   - {key}: {value}")

        return result

    except Exception as e:
        print(f"[ERROR] 에러: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(debug_tts())