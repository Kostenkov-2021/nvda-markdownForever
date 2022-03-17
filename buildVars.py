import subprocess
import time

hashCommit = "unknown"
out = subprocess.check_output(["git", "status", "--porcelain"]).strip().decode()
if not out.strip():
	label = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).strip().decode()
	if len(hashCommit) == 7: hashCommit = label


# Build customizations
# Change this file instead of sconstruct or manifest files, whenever possible.

# Full getext (please don't change)
_ = lambda x : x

# Add-on information variables
addon_info = {
	# for previously unpublished addons, please follow the community guidelines at:
	# https://bitbucket.org/nvdaaddonteam/todo/raw/master/guideLines.txt
	# add-on Name, internal for nvda
	"addon_name" : "markdownForever",
	# Add-on summary, usually the user visible name of the addon.
	# Translators: Summary for this add-on to be shown on installation and add-on information.
	"addon_summary" : _("Markdown Forever"),
	# Add-on description
	# Translators: Long description to be shown for this add-on on add-on information from add-ons manager
	"addon_description" : _("Full-featured Markdown and HTML converter for NVDA"),
	# version
	"addon_version" : time.strftime('%y.%m.%d:') + hashCommit,
	# Author(s)
	"addon_author" : "André <dev@andreabc.net>, Sof <hellosof@gmail.com> and other contributors",
	# URL for the add-on documentation support
	"addon_url" : "https://andreabc.net/projects/NVDA_addons/markdownForever/",
	# Documentation file name
	"addon_docFileName" : None,
	# Minimum NVDA version supported (e.g. "2018.3")
	"addon_minimumNVDAVersion" : "2019.3.0",
	# Last NVDA version supported/tested (e.g. "2018.4", ideally more recent than minimum version)
	"addon_lastTestedNVDAVersion" : "2022.1",
	# Add-on update channel (default is stable or None)
	"addon_updateChannel" : None,
}


import os.path

# Define the python files that are the sources of your add-on.
# You can use glob expressions here, they will be expanded.
pythonSources = [os.path.join("addon", "*.py"),
os.path.join("addon", "globalPlugins", "markdownForever", "*.py")]

# Files that contain strings for translation. Usually your python sources
i18nSources = pythonSources + ["buildVars.py"]

# Files that will be ignored when building the nvda-addon file
# Paths are relative to the addon directory, not to the root directory of your addon sources.
excludedFiles = []
