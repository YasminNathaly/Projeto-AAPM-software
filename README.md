Projeto aapm senai
FastAPI
##python -m uvicorn main:app --reload

python -c "
from main import app

def listar(routes, prefixo=''):
    for r in routes:
        path = getattr(r, 'path', None)
        methods = getattr(r, 'methods', None)
        if path and 'produto' in path:
            print(path, methods)
        sub = getattr(r, 'routes', None)
        if sub:
            listar(sub, prefixo + '  ')

listar(app.routes)
"

Get-Content .\app\models\variacao.py

pip install "bcrypt==3.2.2" --force-reinstall
pip install bcrypt

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt