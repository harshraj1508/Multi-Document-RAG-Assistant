"""End-to-end RAG tests: upload -> list -> chat (with citations) -> memory."""


def _upload(auth_client, name, text, namespace="default"):
    return auth_client.post(
        "/documents",
        files={"file": (name, text.encode())},
        data={"namespace": namespace},
    )


def test_upload_and_list(auth_client):
    r = _upload(auth_client, "cats.txt", "Cats are small furry animals. " * 20)
    assert r.status_code == 201
    assert r.json()["chunk_count"] >= 1

    r = auth_client.get("/documents", params={"namespace": "default"})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_chat_returns_answer_with_citations(auth_client):
    _upload(auth_client, "space.txt", "The sun is a star at the center of the solar system.")
    r = auth_client.post(
        "/chat", json={"question": "What is the sun?", "namespace": "default"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["answer"]
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["filename"] == "space.txt"


def test_namespace_isolation(auth_client):
    _upload(auth_client, "a.txt", "Alpha content about dogs.", namespace="ns1")
    _upload(auth_client, "b.txt", "Beta content about planes.", namespace="ns2")

    # ns1 should only see its own document.
    r = auth_client.get("/documents", params={"namespace": "ns1"})
    assert len(r.json()) == 1
    assert r.json()[0]["filename"] == "a.txt"


def test_conversation_memory_persists(auth_client):
    _upload(auth_client, "m.txt", "Mercury is the closest planet to the sun.")
    r1 = auth_client.post(
        "/chat", json={"question": "Tell me about Mercury", "namespace": "default"}
    )
    session_id = r1.json()["session_id"]

    # Continue the same session.
    auth_client.post(
        "/chat",
        json={"question": "And again?", "namespace": "default", "session_id": session_id},
    )

    r = auth_client.get(f"/chat/sessions/{session_id}")
    assert r.status_code == 200
    # 2 questions + 2 answers = 4 messages.
    assert len(r.json()["messages"]) == 4


def test_delete_document(auth_client):
    doc_id = _upload(auth_client, "d.txt", "to be deleted").json()["id"]
    r = auth_client.delete(f"/documents/{doc_id}")
    assert r.status_code == 204
    assert auth_client.get("/documents").json() == []


def test_health_and_metrics(auth_client):
    assert auth_client.get("/health").json()["status"] == "ok"
    assert "documents" in auth_client.get("/metrics").json()
