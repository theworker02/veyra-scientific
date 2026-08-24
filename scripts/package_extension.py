"""Build a dependency-free VSIX for the bundled Veyra Workbench extension."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extensions" / "veyra-workbench"
OUTPUT = ROOT / "dist" / "veyra-workbench.vsix"


def main() -> None:
    package = json.loads((EXTENSION / "package.json").read_text(encoding="utf-8"))
    identity = f"{package['publisher']}.{package['name']}"
    manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Id="{escape(identity)}" Version="{escape(package['version'])}" Language="en-US" Publisher="{escape(package['publisher'])}" />
    <DisplayName>{escape(package['displayName'])}</DisplayName>
    <Description xml:space="preserve">{escape(package['description'])}</Description>
    <Tags>science,physics,laboratory</Tags>
    <Categories>Other,Data Science,Testing</Categories>
    <GalleryFlags>Public</GalleryFlags>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{escape(package['engines']['vscode'])}" />
    </Properties>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code" Version="[1.90.0,)" />
  </Installation>
  <Dependencies />
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" />
    <Asset Type="Microsoft.VisualStudio.Content" Path="extension/*" />
  </Assets>
</PackageManifest>
"""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="vsixmanifest" ContentType="text/xml" />
  <Default Extension="json" ContentType="application/json" />
  <Default Extension="js" ContentType="application/javascript" />
  <Default Extension="png" ContentType="image/png" />
  <Default Extension="svg" ContentType="image/svg+xml" />
  <Default Extension="tmLanguage.json" ContentType="application/json" />
  <Default Extension="md" ContentType="text/plain" />
</Types>""")
        archive.writestr("extension.vsixmanifest", manifest)
        for source in EXTENSION.rglob("*"):
            if source.is_file():
                archive.write(source, f"extension/{source.relative_to(EXTENSION).as_posix()}")
    print(OUTPUT)


if __name__ == "__main__":
    main()
