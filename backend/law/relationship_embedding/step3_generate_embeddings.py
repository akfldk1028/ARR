"""
Step 3: 관계 임베딩 생성

목적:
- relationship_contexts.json 로드
- OpenAI text-embedding-3-large로 임베딩 생성 (3072-dim)
- 배치 처리 및 진행 표시
- 결과를 relationship_contexts_with_embeddings.json에 저장
"""

import os
import sys
import django
import json
import time
from pathlib import Path
from typing import List, Dict

# Django 설정
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from src.shared.common_fn import load_embedding_model


def generate_embeddings_batch(texts: List[str], embedding_model) -> List[List[float]]:
    """
    배치로 임베딩 생성

    Args:
        texts: 텍스트 리스트
        embedding_model: 임베딩 모델

    Returns:
        임베딩 리스트
    """
    try:
        embeddings = embedding_model.embed_documents(texts)
        return embeddings
    except Exception as e:
        print(f"    [ERROR] 임베딩 생성 실패: {e}")
        # 개별 재시도
        embeddings = []
        for text in texts:
            try:
                emb = embedding_model.embed_query(text)
                embeddings.append(emb)
            except Exception as e2:
                print(f"    [ERROR] 개별 임베딩 실패: {e2}")
                # 빈 임베딩
                embeddings.append([0.0] * 3072)
        return embeddings


def generate_relationship_embeddings():
    """관계 임베딩 생성 메인 함수"""

    print("=" * 80)
    print("Step 3: 관계 임베딩 생성")
    print("=" * 80)

    # 입력 파일 로드
    input_file = Path(__file__).parent / "data" / "relationship_contexts.json"

    if not input_file.exists():
        print(f"[ERROR] 입력 파일 없음: {input_file}")
        print("  -> Step 2를 먼저 실행하세요: python step2_extract_contexts.py")
        return

    print(f"[1] 입력 파일 로드: {input_file}")
    print("-" * 80)

    with open(input_file, 'r', encoding='utf-8') as f:
        relationship_contexts = json.load(f)

    total_count = len(relationship_contexts)
    print(f"  총 {total_count:,d}개 관계 로드\n")

    # 임베딩 모델 로드
    print("[2] OpenAI 임베딩 모델 로드")
    print("-" * 80)

    try:
        embedding_model, dimension = load_embedding_model("openai")
        print("  [OK] text-embedding-3-large 모델 로드 성공")
        print(f"  차원: {dimension}-dim\n")
    except Exception as e:
        print(f"  [ERROR] 모델 로드 실패: {e}")
        print("  -> .env 파일에서 OPENAI_API_KEY 확인 필요")
        return

    # 배치 처리 설정
    batch_size = 100
    total_batches = (total_count + batch_size - 1) // batch_size

    print("[3] 임베딩 생성 시작")
    print("-" * 80)
    print(f"  배치 크기: {batch_size}")
    print(f"  총 배치: {total_batches}\n")

    # 임베딩 생성
    start_time = time.time()
    success_count = 0
    fail_count = 0

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, total_count)
        batch = relationship_contexts[start_idx:end_idx]

        print(f"  배치 {batch_idx + 1}/{total_batches}: {start_idx:,d} ~ {end_idx:,d}")

        # 텍스트 추출
        texts = [rel['context'] for rel in batch]

        # 임베딩 생성
        try:
            embeddings = generate_embeddings_batch(texts, embedding_model)

            # 결과 저장
            for i, rel in enumerate(batch):
                rel['embedding'] = embeddings[i]
                rel['embedding_dim'] = len(embeddings[i])
                success_count += 1

            print(f"    [OK] {len(batch)}개 임베딩 생성 성공")

        except Exception as e:
            print(f"    [ERROR] 배치 실패: {e}")
            fail_count += len(batch)

        # Rate limiting (OpenAI API)
        if batch_idx < total_batches - 1:
            time.sleep(0.5)  # 0.5초 대기

    elapsed_time = time.time() - start_time

    print()
    print(f"  완료: {success_count:,d}개 성공, {fail_count:,d}개 실패")
    print(f"  소요 시간: {elapsed_time:.1f}초\n")

    # 통계
    print("[4] 임베딩 통계")
    print("-" * 80)

    if success_count > 0:
        # 차원 확인
        dims = [rel.get('embedding_dim', 0) for rel in relationship_contexts if 'embedding' in rel]
        if dims:
            print(f"  임베딩 차원: {dims[0]:,d}")
            print(f"  임베딩 개수: {len(dims):,d}")

            # 의미 타입별 분포
            type_counts = {}
            for rel in relationship_contexts:
                if 'embedding' in rel:
                    sem_type = rel['semantic_type']
                    type_counts[sem_type] = type_counts.get(sem_type, 0) + 1

            print("\n  의미 타입별 임베딩:")
            for sem_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"    {sem_type:15s}: {count:6,d}개")
    print()

    # 출력 파일 저장
    print("[5] 결과 파일 저장")
    print("-" * 80)

    output_file = Path(__file__).parent / "data" / "relationship_contexts_with_embeddings.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(relationship_contexts, f, ensure_ascii=False, indent=2)

    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"  파일: {output_file}")
    print(f"  크기: {file_size_mb:.1f} MB")
    print(f"  개수: {len(relationship_contexts):,d}개\n")

    # 요약
    print("[6] 요약")
    print("=" * 80)
    print(f"  총 관계: {total_count:,d}개")
    print(f"  임베딩 생성: {success_count:,d}개")
    print(f"  실패: {fail_count:,d}개")
    print(f"  소요 시간: {elapsed_time:.1f}초")
    print(f"  결과 파일: {output_file}")
    print()
    print("  다음 단계:")
    print("  -> Step 4: Neo4j 업데이트 (step4_update_neo4j.py)")
    print("=" * 80)


if __name__ == "__main__":
    generate_relationship_embeddings()
