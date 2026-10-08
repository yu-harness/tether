# 把 site/ 的内容推到 tether 仓库的 gh-pages 分支，Pages 从这里发布。
# 重新部署直接跑这个脚本即可；需要 gh 已登录（凭据助手会用 gh auth token）。
$ErrorActionPreference = "Stop"
$tether = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$source = Join-Path $tether "site"
$target = Join-Path $tether "tmp\pages-deploy-site"

if (Test-Path $target) { Remove-Item -Recurse -Force $target }
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item (Join-Path $source "*") -Destination $target -Recurse -Force

Set-Location $target
git init -q -b gh-pages
git add -A
git commit -q -m "tether demo page"
if ($LASTEXITCODE -ne 0) { throw "提交失败，退出码 $LASTEXITCODE" }
git remote add origin https://github.com/yu-harness/tether.git
if ($LASTEXITCODE -ne 0) { throw "添加远端失败，退出码 $LASTEXITCODE" }

$env:GH_TOKEN = (gh auth token).Trim()
git -c credential.helper="!gh auth git-credential" push --force origin gh-pages
if ($LASTEXITCODE -ne 0) { throw "推送失败，退出码 $LASTEXITCODE" }
Write-Output "pushed gh-pages"
