"""法眼识契 — 便携版（浏览器模式，关窗口即停服务）v2.0"""
import sys, os, threading, time, webbrowser, signal
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"

# 工作目录
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

# Tesseract OCR — 优先找打包内置的，再找系统安装的
_TESSDATA_DIRS = [
    Path(BASE_DIR) / "_internal" / "tesseract",
    Path(BASE_DIR) / "tesseract",
]
_TESSERACT_CMD = None
for d in _TESSDATA_DIRS:
    tess_exe = d / "tesseract.exe"
    if tess_exe.exists():
        _TESSERACT_CMD = str(tess_exe)
        os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
        os.environ["TESSDATA_PREFIX"] = str(d / "tessdata")
        break
if not _TESSERACT_CMD:
    # 系统安装的回退
    sys_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(sys_tess):
        _TESSERACT_CMD = sys_tess
        os.environ["PATH"] += os.pathsep + r"C:\Program Files\Tesseract-OCR"

# ============================================================
# 数据 & API（同之前版本，所有路由直写在 launcher）
# ============================================================
from legal_db import get_db
from analyzer import ContractAnalyzer

db = get_db()
analyzer_obj = ContractAnalyzer()

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="法眼识契 API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# OCR 检测（_TESSERACT_CMD 已在上面设置）
_OCR_AVAILABLE = False
if _TESSERACT_CMD and os.path.exists(_TESSERACT_CMD):
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD
        pytesseract.get_tesseract_version()
        _OCR_AVAILABLE = True
    except Exception:
        _OCR_AVAILABLE = False

# ---- 关闭信号 ----
_shutdown_event = threading.Event()

@app.post("/api/shutdown")
async def api_shutdown():
    _shutdown_event.set()
    threading.Thread(target=lambda: os._exit(0), daemon=True).start()
    return {"message": "stopping"}

@app.get("/api/health")
async def health():
    return {"status":"ok","laws_count":len(db.articles),"cases_count":len(db.cases),"rules_count":len(analyzer_obj.rules),"ocr_available":_OCR_AVAILABLE}

@app.get("/api/stats")
async def get_stats():
    return {"laws_count":len(db.articles),"cases_count":len(db.cases),"rules_count":len(analyzer_obj.rules),"categories":list(db.get_categories().values())}

# ---- 法律条文 ----
@app.get("/api/laws")
async def get_laws(category:str=None, keyword:str=None):
    if category and category != "all": articles = db.search_by_category(category)
    elif keyword and keyword.strip(): articles = db.search_articles(keyword.strip())
    else: articles = db.articles
    return {"total":len(articles), "articles":articles}

@app.get("/api/laws/categories")
async def get_categories():
    return {"categories": db.get_categories()}

@app.get("/api/laws/{article_no:path}")
async def get_article(article_no:str):
    art = db.get_article(article_no)
    if not art: raise HTTPException(404, "条文未找到")
    return art

# ---- 判例 ----
@app.get("/api/cases")
async def get_cases(keyword:str=None):
    if keyword and keyword.strip(): cases = db.search_cases(keyword.strip())
    else: cases = db.cases
    return {"total":len(cases), "cases":cases}

@app.get("/api/cases/{case_id:path}")
async def get_case(case_id:str):
    case = db.get_case(case_id)
    if not case: raise HTTPException(404, "判例未找到")
    return case

# ---- 合同分析 ----
@app.post("/api/analyze")
async def analyze(text:str=Form(...), contract_type:str=Form("买卖合同"), side:str=Form("neutral")):
    if not text or len(text.strip()) < 10: raise HTTPException(400, "合同文本太短")
    if side not in ("a","b","neutral"): side = "neutral"
    return analyzer_obj.analyze(text, contract_type, side)

@app.post("/api/analyze/file")
async def analyze_file(file:UploadFile=File(...), contract_type:str=Form("买卖合同"), side:str=Form("neutral")):
    content = await file.read()
    text = None
    # .docx 是 ZIP 压缩的 XML，需用 python-docx 解析
    if file.filename and file.filename.lower().endswith('.docx'):
        try:
            import docx
            import io as _io
            doc = docx.Document(_io.BytesIO(content))
            text = '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            raise HTTPException(400, f"无法解析Word文档: {str(e)}")
    else:
        # 纯文本解析
        try: text = content.decode("utf-8")
        except UnicodeDecodeError:
            try: text = content.decode("gbk")
            except: text = content.decode("utf-8", errors="replace")
    if not text or len(text.strip()) < 10:
        raise HTTPException(400, "文件内容太短或无法识别")
    return analyzer_obj.analyze(text, contract_type, side)

# ---- OCR ----
@app.post("/api/ocr")
async def ocr_recognize(file:UploadFile=File(...)):
    if not _OCR_AVAILABLE: raise HTTPException(501, "OCR引擎未安装，请通过文本方式输入合同内容")
    import pytesseract, io
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD
    content = await file.read()
    try:
        image = Image.open(io.BytesIO(content))
        text = pytesseract.image_to_string(image, lang='chi_sim')
        data = pytesseract.image_to_data(image, lang='chi_sim', output_type=pytesseract.Output.DICT)
        confidences = [int(c) for c in data['conf'] if c != '-1']
        avg_conf = sum(confidences)/len(confidences)/100 if confidences else 0
        return {"text":text.strip(),"confidence":round(avg_conf,3),"chars":len(text.strip()),"ocr_available":True}
    except Exception as e: raise HTTPException(500, f"OCR识别失败: {str(e)}")

# ---- 静态文件 ----
# 静态文件目录（onedir 打包时在 _internal/ 下）
_STATIC_CANDIDATES = [
    Path(BASE_DIR) / "static",
    Path(BASE_DIR) / "_internal" / "static",
]
STATIC_DIR = None
for d in _STATIC_CANDIDATES:
    if d.exists():
        STATIC_DIR = d
        break
if STATIC_DIR:
    app.mount("/app", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
async def serve_frontend():
    if STATIC_DIR:
        index = STATIC_DIR / "index.html"
        if index.exists():
            return HTMLResponse(content=index.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>法眼识契</h1><p>正在加载...</p>")

# ============================================================
# 启动入口
# ============================================================
if __name__ == "__main__":
    import urllib.request

    print("=" * 50)
    print("  法眼识契 — 合同风险智能把控系统")
    print(f"  法律条文: {len(db.articles)} 条  |  判例: {len(db.cases)} 个  |  规则: {len(analyzer_obj.rules)} 条")
    print(f"  OCR引擎: {'可用' if _OCR_AVAILABLE else '未安装（仍可文本输入）'}")
    print("=" * 50)
    print("  >> 正在启动服务...")
    print("  >> 网页加载后，点顶栏 [停止服务] 退出")
    print("  >> 直接关闭浏览器标签页 = 服务仍在运行")
    print("    如需彻底退出，请关闭本窗口或点 [停止服务]")
    print("=" * 50)

    # 启动 uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=5800, log_level="warning")
    server = uvicorn.Server(config=config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    # 等就绪
    for i in range(30):
        try:
            urllib.request.urlopen("http://127.0.0.1:5800/api/health", timeout=2)
            break
        except Exception:
            time.sleep(1)

    # 打开浏览器
    webbrowser.open("http://127.0.0.1:5800/app")

    # 阻塞等待关闭信号（或用户关控制台窗口）
    try:
        _shutdown_event.wait()
    except KeyboardInterrupt:
        pass

    server.should_exit = True
    print("服务已停止")
