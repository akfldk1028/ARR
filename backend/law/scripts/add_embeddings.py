"""
Phase 2: Neo4j HANG 노드에 임베딩 추가

Neo4j에 이미 저장된 HANG 노드의 content를 읽어서
sentence-transformers로 임베딩을 생성하고
각 HANG 노드에 embedding 속성을 추가합니다.

사용법:
    python add_embeddings.py

환경 변수 (.env 파일):
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=your_password
    NEO4J_DATABASE=neo4j
"""

import os
import sys
from pathlib import Path
from typing import List, Dict
import logging

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# .env 파일 로드 (프로젝트 루트에서 찾기)
env_path = project_root.parent / '.env'  # backend/.env
if not env_path.exists():
    env_path = project_root / '.env'  # law/.env (fallback)

if env_path.exists():
    load_dotenv(env_path)
    logger.info(f".env 파일 로드: {env_path}")
else:
    logger.warning(f".env 파일 없음. 환경 변수 직접 설정 필요: {env_path}")


class EmbeddingAdder:
    """Neo4j HANG 노드에 임베딩 추가"""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        model_name: str = "jhgan/ko-sbert-sts"
    ):
        """
        Args:
            uri: Neo4j URI (예: bolt://localhost:7687)
            user: Neo4j 사용자명
            password: Neo4j 비밀번호
            database: 데이터베이스 이름 (기본: neo4j)
            model_name: Sentence-Transformers 모델명 (기본: jhgan/ko-sbert-sts)
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

        logger.info(f"Neo4j 연결 성공: {uri}")
        logger.info(f"임베딩 모델 로드 중: {model_name}...")
        self.model = SentenceTransformer(model_name)
        logger.info(f"임베딩 모델 로드 완료 (차원: {self.model.get_sentence_embedding_dimension()})")

    def close(self):
        """Neo4j 연결 종료"""
        self.driver.close()
        logger.info("Neo4j 연결 종료")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_hang_nodes_count(self) -> int:
        """HANG 노드 개수 확인"""
        with self.driver.session(database=self.database) as session:
            result = session.run("MATCH (h:HANG) RETURN count(h) as count")
            count = result.single()["count"]
            logger.info(f"총 HANG 노드 개수: {count:,}개")
            return count

    def fetch_hang_nodes(self, batch_size: int = 100) -> List[Dict]:
        """
        HANG 노드를 배치로 가져오기

        Args:
            batch_size: 한 번에 가져올 노드 개수

        Yields:
            HANG 노드 배치 리스트
        """
        with self.driver.session(database=self.database) as session:
            offset = 0
            while True:
                result = session.run("""
                    MATCH (h:HANG)
                    RETURN
                        h.full_id as full_id,
                        h.content as content,
                        h.number as number,
                        h.law_name as law_name
                    ORDER BY h.full_id
                    SKIP $offset
                    LIMIT $batch_size
                """, offset=offset, batch_size=batch_size)

                nodes = [record.data() for record in result]

                if not nodes:
                    break

                yield nodes
                offset += batch_size

    def add_embeddings_to_hang_nodes(self, batch_size: int = 100, embedding_batch_size: int = 32):
        """
        모든 HANG 노드에 임베딩 추가

        Args:
            batch_size: Neo4j에서 가져올 노드 배치 크기
            embedding_batch_size: 임베딩 생성 배치 크기 (메모리 효율)
        """
        total_count = self.get_hang_nodes_count()

        if total_count == 0:
            logger.warning("HANG 노드가 없습니다. Neo4j에 데이터를 먼저 로드하세요.")
            return

        processed = 0

        logger.info(f"임베딩 추가 시작 (총 {total_count:,}개 노드)")
        logger.info(f"배치 크기: Neo4j={batch_size}, 임베딩={embedding_batch_size}")

        with self.driver.session(database=self.database) as session:
            for hang_batch in self.fetch_hang_nodes(batch_size):
                # content 추출
                contents = [node['content'] for node in hang_batch if node['content']]
                full_ids = [node['full_id'] for node in hang_batch if node['content']]

                if not contents:
                    logger.warning(f"배치에 content가 없는 노드들: {len(hang_batch)}개")
                    continue

                # 임베딩 생성 (배치 처리)
                embeddings = self.model.encode(
                    contents,
                    batch_size=embedding_batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True
                )

                # Neo4j에 임베딩 업데이트
                for full_id, embedding in zip(full_ids, embeddings):
                    session.run("""
                        MATCH (h:HANG {full_id: $full_id})
                        SET h.embedding = $embedding
                    """, full_id=full_id, embedding=embedding.tolist())

                processed += len(contents)
                progress = (processed / total_count) * 100
                logger.info(f"진행: {processed:,}/{total_count:,} ({progress:.1f}%) - 마지막: {full_ids[-1]}")

        logger.info(f"✅ 임베딩 추가 완료: {processed:,}개 노드")

    def create_vector_index(self, index_name: str = "hang_embedding_index"):
        """
        HANG 노드의 embedding 속성에 벡터 인덱스 생성

        Args:
            index_name: 인덱스 이름
        """
        logger.info(f"벡터 인덱스 생성 중: {index_name}")

        with self.driver.session(database=self.database) as session:
            # 기존 인덱스 확인
            result = session.run("SHOW INDEXES")
            existing_indexes = [record['name'] for record in result]

            if index_name in existing_indexes:
                logger.info(f"벡터 인덱스가 이미 존재함: {index_name}")
                return

            # 벡터 인덱스 생성
            try:
                session.run(f"""
                    CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                    FOR (h:HANG) ON (h.embedding)
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: 768,
                            `vector.similarity_function`: 'cosine'
                        }}
                    }}
                """)
                logger.info(f"✅ 벡터 인덱스 생성 완료: {index_name}")
            except Exception as e:
                logger.error(f"벡터 인덱스 생성 실패: {e}")
                raise

    def verify_embeddings(self, sample_size: int = 5):
        """
        임베딩이 올바르게 추가되었는지 샘플 확인

        Args:
            sample_size: 확인할 샘플 개수
        """
        logger.info(f"임베딩 검증 중 (샘플 {sample_size}개)")

        with self.driver.session(database=self.database) as session:
            # 임베딩이 있는 노드 개수
            result = session.run("""
                MATCH (h:HANG)
                WHERE h.embedding IS NOT NULL
                RETURN count(h) as count
            """)
            with_embedding = result.single()["count"]

            # 임베딩이 없는 노드 개수
            result = session.run("""
                MATCH (h:HANG)
                WHERE h.embedding IS NULL
                RETURN count(h) as count
            """)
            without_embedding = result.single()["count"]

            logger.info(f"임베딩 있음: {with_embedding:,}개")
            logger.info(f"임베딩 없음: {without_embedding:,}개")

            # 샘플 노드 확인
            result = session.run(f"""
                MATCH (h:HANG)
                WHERE h.embedding IS NOT NULL
                RETURN
                    h.full_id as full_id,
                    size(h.embedding) as embedding_dim,
                    substring(h.content, 0, 50) as content_sample
                LIMIT {sample_size}
            """)

            logger.info("\n샘플 노드:")
            for record in result:
                logger.info(f"  - {record['full_id']}")
                logger.info(f"    임베딩 차원: {record['embedding_dim']}")
                logger.info(f"    내용 샘플: {record['content_sample']}...")

            if with_embedding == 0:
                logger.error("❌ 임베딩이 추가된 노드가 없습니다!")
                return False

            logger.info(f"✅ 검증 완료: {with_embedding:,}개 노드에 임베딩 추가됨")
            return True


def main():
    """메인 실행 함수"""
    # 환경 변수 읽기
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    if not password:
        logger.error("NEO4J_PASSWORD 환경 변수가 설정되지 않았습니다!")
        logger.error(".env 파일을 생성하거나 환경 변수를 설정하세요.")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Phase 2: Neo4j HANG 노드에 임베딩 추가")
    logger.info("=" * 60)

    try:
        with EmbeddingAdder(uri, user, password, database) as adder:
            # 1. 임베딩 추가
            adder.add_embeddings_to_hang_nodes(
                batch_size=100,           # Neo4j 배치 크기
                embedding_batch_size=32   # 임베딩 생성 배치 크기
            )

            # 2. 벡터 인덱스 생성
            adder.create_vector_index(index_name="hang_embedding_index")

            # 3. 검증
            success = adder.verify_embeddings(sample_size=5)

            if success:
                logger.info("\n" + "=" * 60)
                logger.info("🎉 Phase 2 완료!")
                logger.info("=" * 60)
                logger.info("다음 단계: Multi-Agent RAG 시스템 구현")
            else:
                logger.error("검증 실패. 로그를 확인하세요.")
                sys.exit(1)

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
