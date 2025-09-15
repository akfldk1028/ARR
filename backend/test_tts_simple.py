#!/usr/bin/env python3
"""
Gemini TTS API Simple Test Script
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


async def test_tts_basic():
    """기본 TTS 테스트"""
    print("[TTS] 기본 TTS 테스트 시작...")

    try:
        service = get_gemini_service()

        # 간단한 텍스트로 테스트
        test_message = "Hello! This is a TTS test message."

        print(f"[메시지] 테스트 메시지: {test_message}")
        print("[처리] 음성 생성 중...")

        result = await service.process_text_with_audio(
            message=test_message,
            voice_name="Aoede"
        )

        print(f"[결과] 완료:")
        print(f"   - 성공: {result['success']}")
        print(f"   - 모델: {result['model']}")
        print(f"   - 음성: {result.get('voice', 'Unknown')}")
        print(f"   - 응답 시간: {result['response_time']:.2f}초")
        print(f"   - 전사: {result.get('transcript', 'No transcript')}")
        print(f"   - 오디오 데이터: {'있음' if result.get('audio') else '없음'}")

        if result.get('audio'):
            print(f"   - 오디오 크기: {len(result['audio'])} bytes")

        return result['success']

    except Exception as e:
        print(f"[ERROR] 에러 발생: {e}")
        return False


async def test_voices():
    """여러 음성 테스트"""
    print("\n[VOICES] 음성 테스트...")

    voices = ["Aoede", "Charon", "Kore"]
    service = get_gemini_service()

    for voice in voices:
        print(f"[{voice}] 테스트 중...")
        try:
            result = await service.process_text_with_audio(
                message=f"안녕하세요, {voice} 음성입니다.",
                voice_name=voice
            )

            status = "SUCCESS" if result['success'] else "FAILED"
            print(f"   [{voice}] {status} - {result['response_time']:.2f}초")

        except Exception as e:
            print(f"   [{voice}] ERROR - {str(e)[:50]}...")


async def main():
    """메인 테스트 실행"""
    print("[MAIN] Gemini TTS API 테스트")
    print("=" * 40)

    # 1. 기본 테스트
    success = await test_tts_basic()

    if success:
        # 2. 음성 테스트
        await test_voices()

    print("\n[COMPLETE] 테스트 완료!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] 테스트 중단됨")
    except Exception as e:
        print(f"\n[ERROR] 예상치 못한 에러: {e}")