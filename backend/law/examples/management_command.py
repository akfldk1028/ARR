"""
Django Management Command 예시

파일 위치: law_rag/management/commands/load_embeddings.py
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from law_rag.core.neo4j_manager import Neo4jLawLoader
from sentence_transformers import SentenceTransformer
import json


class Command(BaseCommand):
    help = 'Neo4j에 임베딩 데이터 로드'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='기존 데이터 삭제 후 로드'
        )

    def handle(self, *args, **options):
        self.stdout.write("임베딩 데이터 로드 시작...")

        # Neo4j 연결
        with Neo4jLawLoader(**settings.NEO4J_CONFIG) as loader:
            with loader.driver.session(database=loader.database) as session:

                if options['clear']:
                    self.stdout.write("기존 Chunk 노드 삭제 중...")
                    session.run("MATCH (c:Chunk) DETACH DELETE c")

                # 임베딩 파일 로드
                embedding_files = settings.RAG_DATA_DIR.glob("*_with_embeddings.json")

                total_chunks = 0
                for file in embedding_files:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    chunks = data['chunks']

                    # 배치 로드
                    batch_size = 100
                    for i in range(0, len(chunks), batch_size):
                        batch = chunks[i:i+batch_size]

                        session.run("""
                            UNWIND $chunks AS chunk
                            CREATE (c:Chunk {
                                chunk_id: chunk.chunk_id,
                                content: chunk.content,
                                embedding: chunk.embedding,
                                law_name: chunk.metadata.law_name,
                                jo_title: chunk.metadata.jo_title
                            })
                        """, chunks=batch)

                        total_chunks += len(batch)

                    self.stdout.write(f"✓ {file.name}: {len(chunks)}개")

                # Vector Index 생성
                self.stdout.write("Vector Index 생성 중...")
                session.run("""
                    CREATE VECTOR INDEX vector IF NOT EXISTS
                    FOR (c:Chunk) ON (c.embedding)
                    OPTIONS {indexConfig: {
                        `vector.dimensions`: 768,
                        `vector.similarity_function`: 'cosine'
                    }}
                """)

        self.stdout.write(
            self.style.SUCCESS(f'완료! 총 {total_chunks}개 Chunk 로드됨')
        )


# 사용법:
# python manage.py load_embeddings
# python manage.py load_embeddings --clear
