# -*- coding: utf-8 -*-
"""把合同 HTML 打成「电子版 PDF」和「像扫描件的图片型 PDF」。"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

HERE = Path(__file__).resolve().parent
HTML = HERE / "模拟采购合同.html"
ELEC = HERE / "模拟采购合同-电子版.pdf"
SCAN = HERE / "模拟采购合同-扫描件.pdf"


def _chrome() -> str:
    # Linux / macOS：PATH 上的常见名字
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    # Windows 标准安装位置 / macOS .app
    for p in (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ):
        if p.exists():
            return str(p)
    raise RuntimeError("找不到 Chrome/Chromium/Edge，请先安装其中之一")


def build_electronic() -> Path:
    subprocess.run(
        [
            _chrome(), "--headless", "--no-sandbox", "--disable-gpu",
            "--no-pdf-header-footer", f"--print-to-pdf={ELEC}",
            "--virtual-time-budget=4000", HTML.as_uri(),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90,
    )
    print("electronic", ELEC, ELEC.stat().st_size)
    return ELEC


def _pdf_to_pngs(pdf: Path, out_dir: Path) -> list[Path]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("需要 pdftoppm（Linux: poppler-utils；Windows: 安装 poppler 并把 bin 目录加入 PATH）才能做扫描件")
    prefix = out_dir / "page"
    subprocess.run(
        [pdftoppm, "-png", "-r", "150", str(pdf), str(prefix)],
        check=True, timeout=60,
    )
    return sorted(out_dir.glob("page-*.png")) or sorted(out_dir.glob("page*.png"))


def _make_scan_like(src: Path) -> Image.Image:
    im = Image.open(src).convert("RGB")
    # 轻微旋转，模拟拍歪 / 复印歪
    im = im.rotate(0.7, resample=Image.BICUBIC, expand=True, fillcolor=(232, 228, 220))
    im = ImageOps.autocontrast(im, cutoff=1)
    im = ImageEnhance.Color(im).enhance(0.35)          # 去色，像复印件
    im = ImageEnhance.Contrast(im).enhance(1.15)
    im = ImageEnhance.Brightness(im).enhance(1.04)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))
    # 加一点噪点
    noise = Image.effect_noise(im.size, 12).convert("L")
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    im = Image.blend(im, noise_rgb, 0.08)
    # JPEG 再压一遍，做出扫描件块状感
    buf = tempfile.SpooledTemporaryFile()
    im.save(buf, format="JPEG", quality=42)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def build_scan(elec: Path) -> Path:
    with tempfile.TemporaryDirectory() as td:
        pages = _pdf_to_pngs(elec, Path(td))
        if not pages:
            raise RuntimeError("pdftoppm 没有产出页面")
        scans = [_make_scan_like(p) for p in pages]
        scans[0].save(
            SCAN, save_all=True, append_images=scans[1:], resolution=150,
        )
    print("scan", SCAN, SCAN.stat().st_size)
    return SCAN


if __name__ == "__main__":
    elec = build_electronic()
    build_scan(elec)
