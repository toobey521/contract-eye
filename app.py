"""
法眼识契 — 合同风险智能把控系统
FastAPI 后端服务
"""

import sys
import os
import json
import base64
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from legal_db import get_db, LAW_ARTICLES, CASES
from analyzer import analyze_contract, ContractAnalyzer

app = FastAPI(title="法眼识契 API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================== 数据初始化 ========================
db = get_db()
analyzer = ContractAnalyzer()

# ======================== OCR 引擎 ========================
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_AVAILABLE = os.path.exists(TESSERACT_CMD)

# 全局 uvicorn server 引用（用于优雅关闭）
_uvicorn_server = None

def set_server(srv):
    global _uvicorn_server
    _uvicorn_server = srv

if TESSERACT_AVAILABLE:
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        # 测试
        test = pytesseract.get_tesseract_version()
        print(f"[OCR] Tesseract v{test} 可用")
    except Exception as e:
        TESSERACT_AVAILABLE = False
        print(f"[OCR] pytesseract 加载失败: {e}")
else:
    print("[OCR] Tesseract 未安装，OCR 功能不可用")


# 关闭服务端点
import signal as _sig, threading as _thr
@app.post("/api/shutdown")
async def _stop():
    _thr.Thread(target=lambda: __import__('os').kill(__import__('os').getpid(), _sig.SIGTERM), daemon=True).start()
    return {"message": "stopping"}

# ======================== API 路由 ========================

@app.get("/")
async def root():
    return {"message": "法眼识契 API", "version": "1.0.0", "status": "running"}

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "laws_count": len(db.articles),
        "cases_count": len(db.cases),
        "rules_count": len(analyzer.rules),
        "ocr_available": TESSERACT_AVAILABLE
    }



# ---- 法律数据库 API ----

@app.get("/api/laws")
async def get_laws(category: str = None, keyword: str = None):
    """获取法律条文列表"""
    if category and category != "all":
        articles = db.search_by_category(category)
    elif keyword and keyword.strip():
        articles = db.search_articles(keyword.strip())
    else:
        articles = db.articles

    return {
        "total": len(articles),
        "articles": [{
            "article_no": a["article_no"],
            "law_name": a["law_name"],
            "category": a["category"],
            "chapter": a["chapter"],
            "content": a["content"],
            "keywords": a["keywords"]
        } for a in articles]
    }

@app.get("/api/laws/categories")
async def get_categories():
    """获取法律分类"""
    return {"categories": db.get_categories()}

@app.get("/api/laws/{article_no:path}")
async def get_article(article_no: str):
    """获取具体法律条文"""
    art = db.get_article(article_no)
    if not art:
        raise HTTPException(status_code=404, detail="条文未找到")
    return art

# ---- 判例数据库 API ----

@app.get("/api/cases")
async def get_cases(keyword: str = None):
    """获取判例列表"""
    if keyword and keyword.strip():
        cases = db.search_cases(keyword.strip())
    else:
        cases = db.cases

    return {
        "total": len(cases),
        "cases": cases
    }

@app.get("/api/cases/{case_id:path}")
async def get_case(case_id: str):
    """获取具体判例"""
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="判例未找到")
    return case

# ---- 合同分析 API ----

@app.post("/api/analyze")
async def analyze(
    text: str = Form(...),
    contract_type: str = Form("买卖合同"),
    side: str = Form("neutral")
):
    """分析合同文本风险"""
    if not text or len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="合同文本太短，请提供完整的合同内容")

    if side not in ("a", "b", "neutral"):
        side = "neutral"

    result = analyzer.analyze(text, contract_type, side)
    return result

@app.post("/api/analyze/file")
async def analyze_file(
    file: UploadFile = File(...),
    contract_type: str = Form("买卖合同"),
    side: str = Form("neutral")
):
    """上传合同文件进行分析"""
    content = await file.read()
    
    # 尝试解码
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("gbk")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace")
    
    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="文件内容太短或无法识别")
    
    result = analyzer.analyze(text, contract_type, side)
    return result

@app.post("/api/ocr")
async def ocr_recognize(
    file: UploadFile = File(...)
):
    """OCR 识别合同图片中的文字"""
    if not TESSERACT_AVAILABLE:
        raise HTTPException(status_code=501, detail="OCR引擎未安装，请通过文本方式输入合同内容")

    import pytesseract
    from PIL import Image
    import io

    content = await file.read()
    try:
        image = Image.open(io.BytesIO(content))
        # 中文识别
        text = pytesseract.image_to_string(image, lang='chi_sim')
        # 置信度
        data = pytesseract.image_to_data(image, lang='chi_sim', output_type=pytesseract.Output.DICT)
        confidences = [int(c) for c in data['conf'] if c != '-1']
        avg_conf = sum(confidences) / len(confidences) / 100 if confidences else 0

        return {
            "text": text.strip(),
            "confidence": round(avg_conf, 3),
            "chars": len(text.strip()),
            "ocr_available": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR识别失败: {str(e)}")

# ---- 统计信息 ----

@app.get("/api/stats")
async def get_stats():
    """获取系统统计"""
    return {
        "laws_count": len(db.articles),
        "cases_count": len(db.cases),
        "rules_count": len(analyzer.rules),
        "categories": list(db.get_categories().values())
    }

# ---- 静态文件服务 ----

# 挂载前端页面
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

@app.get("/app", response_class=HTMLResponse)
async def serve_frontend():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>前端文件未找到</h1><p>请确保 static/index.html 存在</p>")


# ======================== 启动 ========================
if __name__ == "__main__":
    print("=" * 50)
    print("  法眼识契 — 合同风险智能把控系统")
    print(f"  法律条文: {len(db.articles)} 条")
    print(f"  判例: {len(db.cases)} 个")
    print(f"  风险规则: {len(analyzer.rules)} 条")
    print(f"  OCR引擎: {'可用' if WINDOWS_OCR_AVAILABLE else '未安装(可使用文本输入)'}")
    print("=" * 50)
    print("  启动地址: http://localhost:5800")
    print("  API文档:  http://localhost:5800/docs")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=5800)
