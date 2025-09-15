#!/usr/bin/env python3
"""
Gemini TTS API Test Script
음성 텍스트-투-스피치 기능을 테스트합니다.
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
        test_message = "안녕하세요! 저는 Gemini AI 어시스턴트입니다. 음성 기능이 잘 작동하고 있나요?"

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


async def test_multiple_voices():
    """여러 음성으로 테스트"""
    print("\n🎭 여러 음성 테스트 시작...")

    voices = ["Aoede", "Charon", "Fenrir", "Kore", "Puck"]
    test_message = "안녕! 나는 {voice} 음성이야!"

    service = get_gemini_service()
    results = {}

    for voice in voices:
        print(f"\n🔊 {voice} 음성 테스트...")
        message = test_message.format(voice=voice)

        try:
            result = await service.process_text_with_audio(
                message=message,
                voice_name=voice
            )

            results[voice] = {
                'success': result['success'],
                'response_time': result['response_time'],
                'has_audio': bool(result.get('audio')),
                'transcript': result.get('transcript', '')
            }

            status = "✅" if result['success'] else "❌"
            print(f"   {status} {voice}: {result['response_time']:.2f}초")

        except Exception as e:
            results[voice] = {'success': False, 'error': str(e)}
            print(f"   ❌ {voice}: 에러 - {e}")

    # 결과 요약
    print(f"\n📊 음성 테스트 결과:")
    successful = sum(1 for r in results.values() if r.get('success', False))
    print(f"   성공: {successful}/{len(voices)}")

    for voice, result in results.items():
        if result.get('success'):
            print(f"   ✅ {voice}: {result['response_time']:.2f}초")
        else:
            print(f"   ❌ {voice}: 실패")

    return results


async def test_long_text():
    """긴 텍스트 TTS 테스트"""
    print("\n📝 긴 텍스트 TTS 테스트...")

    long_text = """
    인공지능은 인간의 학습능력, 추론능력, 지각능력, 그리고 자연언어의 이해능력 등을
    컴퓨터 프로그램으로 실현한 기술입니다. 최근 대화형 AI의 발전으로 인해
    텍스트를 음성으로 변환하는 기술도 놀랍도록 발전했습니다.
    이제 AI는 매우 자연스럽고 인간과 유사한 음성으로 말할 수 있게 되었습니다.
    """

    service = get_gemini_service()

    try:
        print(f"📏 텍스트 길이: {len(long_text)} 문자")
        print("🔄 처리 중...")

        result = await service.process_text_with_audio(
            message=long_text.strip(),
            voice_name="Kore"
        )

        print(f"✅ 긴 텍스트 처리 결과:")
        print(f"   - 성공: {result['success']}")
        print(f"   - 처리 시간: {result['response_time']:.2f}초")
        print(f"   - 오디오: {'생성됨' if result.get('audio') else '실패'}")

        return result['success']

    except Exception as e:
        print(f"❌ 긴 텍스트 처리 실패: {e}")
        return False


async def test_error_handling():
    """에러 처리 테스트"""
    print("\n🚨 에러 처리 테스트...")

    service = get_gemini_service()

    # 빈 메시지 테스트
    try:
        result = await service.process_text_with_audio(
            message="",
            voice_name="Aoede"
        )
        print(f"📭 빈 메시지: {result.get('success', False)}")
    except Exception as e:
        print(f"📭 빈 메시지 에러 처리: {str(e)[:50]}...")

    # 잘못된 음성 이름 테스트
    try:
        result = await service.process_text_with_audio(
            message="잘못된 음성 테스트",
            voice_name="InvalidVoice"
        )
        print(f"🔊 잘못된 음성: {result.get('success', False)}")
    except Exception as e:
        print(f"🔊 잘못된 음성 에러 처리: {str(e)[:50]}...")


async def main():
    """메인 테스트 실행"""
    print("[MAIN] Gemini TTS API 종합 테스트")
    print("=" * 50)

    # 1. 기본 테스트
    basic_success = await test_tts_basic()

    if not basic_success:
        print("❌ 기본 테스트 실패. 추가 테스트를 건너뜁니다.")
        return

    # 2. 여러 음성 테스트
    await test_multiple_voices()

    # 3. 긴 텍스트 테스트
    await test_long_text()

    # 4. 에러 처리 테스트
    await test_error_handling()

    print("\n🎉 모든 테스트 완료!")
    print("💡 웹 인터페이스에서도 테스트해보세요: http://localhost:8001/gemini/")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  테스트 중단됨")
    except Exception as e:
        print(f"\n💥 예상치 못한 에러: {e}")