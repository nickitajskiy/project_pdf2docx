from pathlib import Path
from streamlit.testing.v1 import AppTest
from mathpdf.schema import Mode


def test_ui_modes_no_conversion_on_rerun():
    app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py')).run()
    assert not app.exception
    assert len(app.selectbox[0].options)==3
    assert app.button[0].disabled
    app.selectbox[0].select(Mode.PAGES).run()
    assert not app.exception
    assert 'не редактируются' in app.info[0].value
    assert 'conversion' not in app.session_state
