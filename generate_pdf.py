import os
import subprocess

try:
    import markdown
except ImportError:
    subprocess.run(["pip", "install", "markdown"], check=True)
    import markdown

md_text = open('README.md', encoding='utf-8').read()
html_content = markdown.markdown(md_text, extensions=['extra'])

full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; margin: 40px; color: #1e293b; max-width: 900px; margin: 0 auto; padding: 40px; }}
        h1, h2, h3 {{ color: #4f46e5; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; margin-top: 32px; }}
        code {{ background: #f1f5f9; padding: 2px 4px; border-radius: 4px; color: #e11d48; font-family: monospace; }}
        pre {{ background: #1e293b; padding: 15px; border-radius: 8px; overflow-x: auto; color: #f8fafc; }}
        pre code {{ color: inherit; background: transparent; }}
        a {{ color: #3b82f6; text-decoration: none; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
"""

open('DOCUMENTATION.html', 'w', encoding='utf-8').write(full_html)

# Define paths for Edge or Chrome
browser_paths = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
]

browser_exec = None
for bp in browser_paths:
    if os.path.exists(bp):
        browser_exec = bp
        break

if browser_exec:
    html_path = os.path.abspath('DOCUMENTATION.html')
    pdf_path = os.path.abspath('Documentacao_PBI_AutoDoc.pdf')
    print(f"Generating PDF using browser engine...")
    subprocess.run([browser_exec, '--headless', '--disable-gpu', f'--print-to-pdf={pdf_path}', html_path], check=True)
    print("PDF generated successfully.")
else:
    print("Browser not found to generate PDF.")
