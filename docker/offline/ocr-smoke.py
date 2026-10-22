"""在构建时缓存实际解析器权重，并在断网验证时回读中文识别结果。"""

import argparse
import hashlib
import json
import os
from pathlib import Path


def checksums(directory: Path) -> dict[str, str]:
    """记录缓存内每个模型文件的完整摘要。"""
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "offline-models.json"
    }


def main() -> None:
    """识别固定合成文字，拒绝缺失权重或错误识别。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true", help="仅联网制包时下载并固化权重摘要")
    args = parser.parse_args()
    directory = Path(os.environ["RAPIDOCR_MODEL_DIR"])
    manifest = directory / "offline-models.json"
    if not args.freeze:
        expected = json.loads(manifest.read_text(encoding="utf-8"))
        if not expected or checksums(directory) != expected:
            raise RuntimeError("离线 OCR 权重缺失或摘要不符")

    from PIL import Image, ImageDraw, ImageFont
    from yuxi.knowledge.parser.rapid_ocr import RapidOCRParser

    sample = Image.new("RGB", (1200, 180), "white")
    font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 52)
    ImageDraw.Draw(sample).text((40, 50), "离线文档识别测试 2026", font=font, fill="black")
    result = RapidOCRParser().process_image(sample)
    compact = "".join(result.split())
    if "离线文档识别测试" not in compact or "2026" not in compact:
        raise RuntimeError(f"OCR 未识别预期样例：{result!r}")
    frozen = checksums(directory)
    if len([name for name in frozen if name.endswith(".onnx")]) < 3:
        raise RuntimeError("离线 OCR 缺少检测、分类或识别模型")
    if args.freeze:
        manifest.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ocr": "passed", "text": result, "models": frozen}, ensure_ascii=False))


if __name__ == "__main__":
    main()
