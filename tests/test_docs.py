def test_docs_page_is_public(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_docs_page_shows_configured_models(client):
    html = client.get("/docs").text
    assert "lfm25-8b" in html
    assert "qwen3.5:4b" in html


def test_docs_page_documents_chat_endpoint(client):
    html = client.get("/docs").text
    assert "/v1/chat/completions" in html


def test_docs_page_renders_request_base_url(client):
    html = client.get("/docs").text
    assert "http://testserver" in html


def test_root_serves_the_same_doc(client):
    root = client.get("/")
    assert root.status_code == 200
    assert "/v1/chat/completions" in root.text
