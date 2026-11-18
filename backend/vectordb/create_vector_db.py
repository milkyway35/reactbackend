# 데이터 전처리 및 벡터 스토어 생성
# 실행 : backend 폴더에서 python vectordb/create_vector_db.py

import re
import sys
from pathlib import Path

# 직접 실행해도 backend 폴더의 모듈을 찾을 수 있도록 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import CSVLoader, TextLoader
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from common.config import (
    BRIEF_PATH, DETAIL_PATH, CHROMA_DIR, COLLECTION_NAME, COLLECTION_METADATA, EMBEDDING_MODEL
)

# 정형/비정형 데이터에 공통으로 있는 기본정보 항목
BASIC_FIELDS = {"name": "이름", "vintage": "와인 빈티지", "region": "지역", "price": "가격", "stock": "재고량"}


# '이름: 샤또 마고', '- 이름: 샤또 마고' 형식의 줄에서 기본정보를 뽑음
def parse_basic_info(text):
    info = {}
    for key, label in BASIC_FIELDS.items():
        match = re.search(rf"^(?:- )?{label}:\s*(.+)$", text, re.MULTILINE)
        info[key] = match.group(1).strip() if match else ""

    # 가격/재고 필터에 사용할 숫자값 (가격 단위: 만원)
    # 미정은 키를 생략하면 다시 실행해도 이전 가격이 남으므로 None으로 저장
    price = re.match(r"[\d.]+", info["price"])
    info["price_value"] = float(price.group()) if price else None
    info["stock_value"] = int(info["stock"]) if info["stock"].isdigit() else 0
    return info


# 상세 문서를 '## 번호. 와인이름' 단위로 나눔
# 글자 수로만 자르면 와인 이름이 없는 청크가 생겨 어떤 와인의 설명인지 알 수 없음
def split_by_wine(doc):
    sections = []
    for section in re.split(r"(?m)^(?=## \d+\.)", doc.page_content):
        if not section.startswith("## "):
            continue

        info = parse_basic_info(section)
        pairing = re.search(r"^- 한식 페어링(?:\(.*?\)| 추천):\s*(.+)$", section, re.MULTILINE)
        tasting_note = re.search(r"```\s*\n(.*?)```", section, re.DOTALL)
        info["pairing"] = pairing.group(1).strip() if pairing else ""
        info["tasting_note"] = tasting_note.group(1).strip() if tasting_note else ""

        # 마크다운 기호와 출처 URL을 빼고 검색에 필요한 내용만 임베딩
        page_content = "\n".join([
            f"{info['name']} {info['vintage']}",
            f"이름: {info['name']}",
            f"와인 빈티지: {info['vintage']}",
            f"지역: {info['region']}",
            f"가격: {info['price']}",
            f"재고량: {info['stock']}",
            f"한식 페어링: {info['pairing']}",
            f"테이스팅 노트: {info['tasting_note']}",
        ])
        sections.append(Document(page_content=page_content, metadata=info))
    return sections


# 원본 데이터를 읽어 청크로 나눔 (임베딩 비용이 들지 않는 단계)
def load_chunks():
    # 1. 문서 로드
    brief_loader = CSVLoader(str(BRIEF_PATH), encoding="utf-8-sig")     # 행 1개 = 문서 1개, BOM 제거
    brief_docs = brief_loader.load()
    for doc in brief_docs:
        doc.metadata = parse_basic_info(doc.page_content)

    detail_loader = TextLoader(str(DETAIL_PATH), encoding="utf-8")
    detail_docs = split_by_wine(detail_loader.load()[0])                # 와인 1개 = 문서 1개

    # 2. 청킹
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,             # 청크 크기 설정 (현재 데이터는 와인 1개가 나뉘지 않는 크기)
        chunk_overlap=60            # 청크 겹침 설정
    )

    # 청크 분리
    brief_chunks = text_splitter.split_documents(brief_docs)
    detail_chunks = text_splitter.split_documents(detail_docs)

    # 3. 메타데이터 추가
    for chunk in brief_chunks:
        chunk.metadata["source_type"] = "Structured Data"

    for chunk in detail_chunks:
        chunk.metadata["source_type"] = "Unstructured Data"

    return brief_chunks, detail_chunks


def main():
    brief_chunks, detail_chunks = load_chunks()

    # 4. 모든 청크 합치기
    all_chunks = brief_chunks + detail_chunks

    # 다시 실행해도 중복 저장되지 않도록 청크마다 고정된 id를 사용
    chunk_ids = [f"brief-{i}" for i in range(len(brief_chunks))] + [f"detail-{i}" for i in range(len(detail_chunks))]

    # 5. 임베딩 모델
    embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    # 6. 벡터 스토어 생성
    vector_store = Chroma.from_documents(
        documents=all_chunks,
        embedding=embedding_model,
        ids=chunk_ids,
        collection_name=COLLECTION_NAME,
        collection_metadata=COLLECTION_METADATA,
        persist_directory=CHROMA_DIR
    )

    # 7. 이전 실행에서 남았지만 현재 데이터에는 없는 청크 제거
    stale_ids = set(vector_store.get(include=[])["ids"]) - set(chunk_ids)
    if stale_ids:
        vector_store.delete(ids=list(stale_ids))

    print(f"brief 청크: {len(brief_chunks)}개")
    print(f"detail 청크: {len(detail_chunks)}개")
    print(f"삭제한 이전 청크: {len(stale_ids)}개")


if __name__ == "__main__":
    main()
