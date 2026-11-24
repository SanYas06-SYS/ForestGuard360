import re
from fastapi.testclient import TestClient

def test_page_refresh_loads_versioned_assets():
    from backend.app import app
    client=TestClient(app)
    try:
        page=client.get('/team?updated=1')
        assert page.status_code==200
        assert page.headers['cache-control']=='no-store, max-age=0'
        script=re.search(r'src="(/static/frontend/assets/admin-[A-Za-z0-9_-]+\.js)"',page.text)
        assert script, 'Build the frontend before running this test.'
        code=client.get(script.group(1))
        assert code.status_code==200
        assert 'Delete team' in code.text and 'Remove member' in code.text
        assert 'Five fixed teams' not in code.text
        css=re.search(r'href="(/static/frontend/assets/[^\"]+\.css)"',page.text)
        assert css and client.get(css.group(1)).status_code==200
    finally:client.close()
