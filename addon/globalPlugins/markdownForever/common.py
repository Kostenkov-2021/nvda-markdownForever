# Part of Markdown Forever Add-on for NVDA
# This file is covered by the GNU General Public License.
# See the file LICENSE for more details.
# Copyright 2019-2022 André-Abush Clause, Sof and other contributors. Released under GPL.
# <https://github.com/aaclause/nvda-markdownForever>

from . import virtualDocuments
from logHandler import log
import ui
import versionInfo
from urllib.request import Request, urlopen
import treeInterceptorHandler
import textInfos
import languageHandler
import globalVars
import config
import api
import json
import locale
import re
import os
import ssl
import sys
baseDir = os.path.dirname(__file__)
libs = os.path.join(baseDir, "lib")
sys.path.append(libs)
from bs4 import BeautifulSoup
import yaml
import winClipboard
import markdown2
import html2text
import html2markdown

import time
import gui
import wx


import addonHandler
addonHandler.initTranslation()

IM_actions = {
	"saveResultAs": 0,
	"saveSourceAs": 4,
	"browser": 1,
	"virtualBuffer": 2,
	"copyToClip": 3,
}
IM_actionLabels = [
	_("Save the result as"),
	_("Save the source as"),
	_("Show in browser"),
	_("Show in virtual buffer"),
	_("Copy to clipboard")
]
markdownEngines = ["html2text", "html2markdown"]
markdownEngineLabels = [
	("html2text. " + _("Turn HTML into equivalent Markdown-structured text")),
	("html2markdown. " + _("Conservatively convert html to markdown"))
]

EXTRAS = {
	"break-on-newline": _("Replace single new line characters with <br> when True"),
	"code-friendly": _("Disable _ and __ for em and strong"),
	"cuddled-lists": _("Allow lists to be cuddled to the preceding paragraph"),
	"fenced-code-blocks": _("Allows a code block to not have to be indented by fencing it with '```' on a line before and after"),
	"footnotes": _("Support footnotes as in use on daringfireball.net and implemented in other Markdown processors (tho not in Markdown.pl v1.0.1)"),
	"header-ids": _('Adds "id" attributes to headers. The id value is a slug of the header text'),
	"html-classes": _('Takes a dict mapping html tag names (lowercase) to a string to use for a "class" tag attribute. Currently only supports "pre", "code", "table" and "img" tags'),
	"link-patterns": _("Auto-link given regex patterns in text (e.g. bug number references, revision number references)"),
	"markdown-in-html": _('Allow the use of markdown="1" in a block HTML tag to have markdown processing be done on its contents'),
	"nofollow": _('Add rel="nofollow" to all <a> tags with an href.'),
	"numbering": _("Create counters to number tables, figures, equations and graphs"),
	"pyshell": _("Treats unindented Python interactive shell sessions as <code> blocks"),
	"smarty-pants": _("Fancy quote, em-dash and ellipsis handling"),
	"spoiler": _("A special kind of blockquote commonly hidden behind a click on SO"),
	"strike": _("Parse ~~strikethrough~~ formatting"),
	"target-blank-links": _('Add target="_blank" to all <a> tags with an href. This causes the link to be opened in a new tab upon a click'),
	"tables": _("Tables using the same format as GFM and PHP-Markdown Extra"),
	"tag-friendly": _("Requires atx style headers to have a space between the # and the header text. Useful for applications that require twitter style tags to pass through the parser"),
	"task_list": _("Allows github-style task lists (i.e. check boxes)"),
	"underline": _("Parse --underline-- formatting"),
	"use-file-vars": _("Look for an Emacs-style markdown-extras file variable to turn on Extras"),
	"wiki-tables": _("Google Code Wiki table syntax support"),
	"xml": _("Passes one-liner processing instructions and namespaced XML tags"),
}
sys.path.remove(libs)

_addonDir = os.path.join(baseDir, "..", "..")
addonInfos = addonHandler.Addon(_addonDir).manifest
addonSummary = addonInfos["summary"]
addonVersion = addonInfos["version"]
configDir = "%s/markdownForever" % globalVars.appArgs.configPath
defaultLanguage = languageHandler.getLanguage()
internalAutoNumber = r"\!"
internalTocTag = f":\\tableOfContent:{time.time()}/!$£:"
curDir = os.path.dirname(__file__)
addonPath = '\\'.join(curDir.split('\\')[0:-2])
pathPattern = r"^(?:%|[a-zA-Z]:[\\/])[^:*?\"<>|]+\.html?$"
URLPattern = r"^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$"
minCharTemplateName = 1
maxCharTemplateName = 28


def realpath(path):
	path = path.lower()
	vars = ["appdata", "tmp", "temp", "userprofile"]
	for var in vars:
		path = path.replace("%%%s%%" % var, os.environ[var])
	path = path.replace("%addondir%", addonPath)
	return path


def isPath(path):
	path = realpath(path)
	return os.path.exists(path) and os.path.isdir(path)


def isValidFileName(filename):
	return bool(re.match(r"^[^\\/:*?\"<>|]+$", filename))


def getWindowTitle():
	obj = api.getForegroundObject()
	title = obj.name
	if not isinstance(title, str) or not title or title.isspace():
		title = obj.appModule.appName if obj.appModule else None
	return title


def getText():
	err = ''
	obj = api.getFocusObject()
	treeInterceptor = obj.treeInterceptor
	if isinstance(treeInterceptor, treeInterceptorHandler.DocumentTreeInterceptor) and not treeInterceptor.passThrough:
		obj = treeInterceptor
	try:
		info = obj.makeTextInfo(textInfos.POSITION_SELECTION)
	except (RuntimeError, NotImplementedError):
		info = None
	if not info or info.isCollapsed:
		try:
			text = obj.makeTextInfo(textInfos.POSITION_ALL).text
		except (RuntimeError, NotImplementedError):
			obj = api.getNavigatorObject()
			text = obj.value
	else:
		text = info.text
	isLocalFile = False
	if re.match(pathPattern, text):
		fp = realpath(text)
		if os.path.isfile(fp):
			f = open(fp, "rb")
			raw = f.read()
			if raw.startswith(codecs.BOM_UTF8):
				raw = raw[3:]
			f.close()
			text = raw.decode()
			isLocalFile = True
		else:
			err = _("Invalid file path")
	if not isLocalFile and re.match(URLPattern, text.strip()):
		ctx = ssl.create_default_context()
		ctx.check_hostname = False
		ctx.verify_mode = ssl.CERT_NONE
		try:
			req = Request(text)
			req.add_header("Accept", "text/html")
			req.add_header("Accept-encoding", "identity")
			j = urlopen(req, context=ctx)
			data = j.read()
			possibleEncodings = []
			enc_ = j.headers.get_content_charset("UTF-8")
			log.debug("%s charset found in HTTP headers" % enc_)
			possibleEncodings.append(enc_)
			pattern = r"^.*charset=\"?([0-9a-zA-Z\-]+)\"?.*$"
			try:
				start_ = data.index(b"charset=")
				if start_ >= 0:
					enc_ = data[start_:(
						start_+42)].split(b">")[0].replace(b'"', b"").replace(b'\'', b"")
					enc_ = re.sub(pattern, r"\1", enc_.decode("UTF-8"))
					possibleEncodings.insert(0, enc_)
			except ValueError:
				log.debug(j.headers)
			possibleEncodings.append("UTF-8")
			log.debug("%s charset found in <head> HTML" % enc_)
			for possibleEncoding in possibleEncodings:
				ok = 0
				try:
					log.debug("Trying %s" % possibleEncoding)
					text = data.decode(possibleEncoding)
					ok = 1
					break
				except (LookupError, UnicodeDecodeError) as e:
					log.debug(e)
			if not ok:
				log.error(possibleEncodings)
				err = _("Unable to guess the encoding")
		except BaseException as e:
			err = str(e).strip()
	return text, err


def getMetadataAndTextForMarkDown():
	startTime = time.time()
	res = virtualDocuments.isVirtualDocument()
	if res:
		text, err = virtualDocuments.getAllHTML()
	else:
		text, err = getText()
	if err:
		ui.message(err)
		return None, None
	metadata, text = extractMetadata(text)
	if res:
		metadata["title"] = getWindowTitle()
		metadata["timeGen"] = "%.3f s" % (time.time()-startTime)
	return metadata, text


def escapeHTML(text):
	chars = {
		"&": "&amp;",
		'"': "&quot;",
		"'": "&apos;",
		"<": "&lt;",
		">": "&gt;",
	}
	return "".join(chars.get(c, c) for c in text)


def md2HTML(md, metadata=None):
	extras = getMarkdown2Extras()
	if metadata and metadata["toc"]:
		extras.append("toc")
	return markdown2.markdown(md, extras=extras)


def writeFile(fp, content):
	fp = realpath(fp)
	f = open(fp, "wb")
	f.write(content.encode())
	f.close()


def getFileContent(fp):
	content = ""
	fp = realpath(fp)
	fp_ = realpath(config.conf["markdownForever"]["defaultPath"]) + '/' + fp
	if not os.path.exists(fp) and os.path.exists(fp_):
		fp = fp_
	try:
		f = open(fp, "rb")
		text = f.read().decode("UTF-8")
		metadata, content = extractMetadata(text)
		f.close()
	except BaseException as err:
		msg = _("Unable to include “{filePath}”").format(filePath=fp)
		content = f'<div class="MDF_err" role="complementary">{msg}: {escapeHTML(repr(err))}</div>'
	return content


def backTranslateExtraTags(text):
	soup = BeautifulSoup(text)
	matches = soup.findAll(
		["span", "div"], class_=re.compile(r"^extratag_%.+%$"))
	for match in matches:
		extratag = match["class"][-1].split('_', 1)[-1]
		try:
			match.string.replaceWith(extratag)
			match.unwrap()
		except AttributeError as e:
			log.error(e)
	return str(soup)


def extractMetadata(text):
	o = {
		"before": "",
		"after": ""
	}
	metadata = {}
	end = 1
	if len(text) > 4 and text.startswith("---"):
		ln = text[3]
		if ln in ["\r", "\n"]:
			if ln == "\r" and text[4] == "\n":
				ln = "\r\n"
			try:
				end = (text.index(ln * 2)-3)
				y = text[(3 + len(ln)):end].strip()
				docs = yaml.load_all(y, Loader=yaml.FullLoader)
				for doc in docs:
					metadata = doc
				text = text[end+3:].strip()
			except (ValueError, yaml.parser.ParserError, yaml.scanner.ScannerError) as err:
				metadataBlock = text[0:end+3]
				text = text[end+3:].strip()
				text = f"! {err}\n\n```\n{metadataBlock}\n```\n\n{text}"
	if not isinstance(metadata, dict):
		metadata = {}
	HTMLHead = [
		'<meta name="generator" content="MarkdownForever" />',
		'<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes" />'
	]
	HTMLHeader = []
	metadata = {k.lower(): v for k, v in metadata.items()}
	if "language" in metadata.keys():
		metadata["lang"] = metadata.pop("language")
	if "authors" in metadata.keys():
		metadata["author"] = metadata.pop("authors")
	if not "template" in metadata.keys() or metadata["template"] not in (list(config.conf["markdownForever"]["HTMLTemplates"].copy().keys())+["default", "minimal"]):
		metadata["template"] = config.conf["markdownForever"]["HTMLTemplate"]
	if not "autonumber-headings" in metadata.keys() or not isinstance(metadata["autonumber-headings"], (int, bool)):
		metadata["autonumber-headings"] = config.conf["markdownForever"]["autonumber-headings"]
	if not "title" in metadata.keys() or not isinstance(metadata["title"], (str, str)):
		metadata["title"] = ""
	if not "subtitle" in metadata.keys() or not isinstance(metadata["subtitle"], (str, str)):
		metadata["subtitle"] = ""
	metadata["title"] = str(processExtraTags(
		BeautifulSoup(metadata["title"], "html.parser"))[-1].text)
	if not "toc" in metadata.keys() or not isinstance(metadata["toc"], (int, bool)):
		metadata["toc"] = config.conf["markdownForever"]["toc"]
	if not "toc-back" in metadata.keys() or not isinstance(metadata["toc-back"], str):
		metadata["toc-back"] = config.conf["markdownForever"]["toc-back"]
	if not "extratags" in metadata.keys() or not isinstance(metadata["extratags"], (int, bool)):
		metadata["extratags"] = config.conf["markdownForever"]["extratags"]
	if not "extratags-back" in metadata.keys() or not isinstance(metadata["extratags-back"], (int, bool)):
		metadata["extratags-back"] = config.conf["markdownForever"]["extratags-back"]
	if not "detectExtratags" in metadata.keys() or not isinstance(metadata["detectExtratags"], (int, bool)):
		metadata["detectExtratags"] = config.conf["markdownForever"]["detectExtratags"]
	if not "genMetadata" in metadata.keys() or not isinstance(metadata["genMetadata"], (int, bool)):
		metadata["genMetadata"] = config.conf["markdownForever"]["genMetadata"]
	if not "lang" in metadata.keys() or not isinstance(metadata["lang"],  str):
		metadata["lang"] = defaultLanguage
	if not "mathjax" in metadata.keys() or not isinstance(metadata["mathjax"], (int, bool)):
		metadata["mathjax"] = False
	metadata["path"] = metadata["path"] if "path" in metadata.keys() and isPath(
		metadata["path"]) else config.conf["markdownForever"]["defaultPath"]
	metadata["filename"] = metadata["filename"] if "filename" in metadata.keys() and isValidFileName(
		metadata["filename"]) else "MDF_%s" % time.strftime("%y-%m-%d_-_%H-%M-%S")
	if metadata["mathjax"]:
		HTMLHead.append(
			'<script src="http://cdn.mathjax.org/mathjax/latest/MathJax.js?config=TeX-AMS-MML_HTMLorMML" type="text/javascript"></script>')
	if "title" in metadata.keys():
		HTMLHead.append("<title>%s</title>" % metadata["title"])
		HTMLHeader.append('<h1 class="title">%s</h1>' % metadata["title"])
	if "subtitle" in metadata:
		HTMLHeader.append('<p class="subtitle">%s</p>' % metadata["subtitle"])
	if "keywords" in metadata.keys():
		HTMLHead.append('<meta name="keywords" content="%s" />' %
						metadata["keywords"])
	if "author" in metadata.keys():
		if isinstance(metadata["author"], (str, str)):
			metadata["author"] = [metadata["author"]]
		for author in metadata["author"]:
			HTMLHeader.append('<p class="author">%s</p>' % md2HTML(author))
			author_ = str(processExtraTags(
				BeautifulSoup(author, "html.parser"))[-1].text)
			HTMLHead.append('<meta name="author" content="%s" />' % author_)
	if "css" in metadata.keys():
		if isinstance(metadata["css"], (str, str)):
			metadata["css"] = [metadata["css"]]
		for css in metadata["css"]:
			HTMLHead.append('<link rel="stylesheet" href="%s" />' %
							realpath(css))
	includes_keys = ["include-after", "include-before"]
	for include_key in includes_keys:
		if include_key in metadata.keys():
			if isinstance(metadata[include_key], (str, str)):
				metadata[include_key] = [metadata[include_key]]
			for fp in metadata[include_key]:
				o[include_key.split('-')[1]] += getFileContent(fp)
	if "date" in metadata.keys():
		HTMLHeader.append('<p class="date">%s</p>' % metadata["date"])
		HTMLHead.append(
			'<meta name="dcterms.date" content="%s" />' % metadata["date"])
	metadata["HTMLHead"] = '\n'.join(HTMLHead)
	if not HTMLHeader:
		HTMLHeader = ""
	else:
		metadata["HTMLHeader"] = '\n'.join(HTMLHeader)
	return metadata, o["before"] + '\n' + text + '\n' + o["after"]


def getHTMLTemplate(name=None):
	if not name:
		name = config.conf["markdownForever"]["HTMLTemplate"]
	name = name.lower()
	if name == "minimal":
		return {
			"name": "minimal",
			"description": "",
			"content": "{body}"
		}
	HTMLTemplateDir = realpath(f"{configDir}/{name}.tpl")
	if name != "default" and os.path.isfile(HTMLTemplateDir):
		fp = HTMLTemplateDir
	else:
		fp = os.path.join(curDir, "res", "default.tpl")
	with open(fp) as readFile:
		templateEntry = json.load(readFile)
		return templateEntry


def getHTMLTemplates():
	HTMLTemplates = config.conf["markdownForever"]["HTMLTemplates"].copy()
	return [("minimal. " + _("Just the HTML from your Markdown")), ("default. " + _("A minimal template provided by the add-on"))] + list(HTMLTemplates.keys())


def getDefaultHTMLTemplateID(name=None):
	if not name:
		name = config.conf["markdownForever"]["HTMLTemplate"]
	if name == "minimal":
		return 0
	elif name == "default":
		return 1
	else:
		HTMLTemplates = getHTMLTemplates()[2:]
		if name in HTMLTemplates:
			HTMLTemplateID = HTMLTemplates.index(name)
		else:
			HTMLTemplateID = 1
		return HTMLTemplateID


def getHTMLTemplateFromID(idTemplate):
	if idTemplate == 0:
		return "minimal"
	elif idTemplate == 1:
		return "default"
	else:
		return getHTMLTemplates()[idTemplate]


def getReplacements(lang):
	try:
		if lang:
			locale.setlocale(locale.LC_ALL, lang)
	except locale.Error as err:
		log.error(err)
	replacements = [
		("%day%", time.strftime("%A"), 1),
		("%Day%", time.strftime("%A").capitalize(), 1),
		("%dday%", time.strftime("%d"), 1),
		("%month%", time.strftime("%B"), 1),
		("%Month%", time.strftime("%B").capitalize(), 1),
		("%dmonth%", time.strftime("%m"), 1),
		("%year%", time.strftime("%y").capitalize(), 1),
		("%Year%", time.strftime("%Y").capitalize(), 1),
		("%date%", time.strftime("%x"), 1),
		("%time%", time.strftime("%X"), 1),
		("%now%", time.strftime("%c"), 1),
		("%addonVersion%", addonInfos["version"], 1),
		("%markdown2Version%", markdown2.__version__, 1),
		("%html2textVersion%", '.'.join(map(str, html2text.__version__)), 1),
		("%NVDAVersion%", versionInfo.version, 1),
		("%toc%", internalTocTag, 0)
	]
	locale.setlocale(locale.LC_ALL, locale.getdefaultlocale()[0])
	return replacements


def processExtraTags(soup, lang='', allRepl=True, allowBacktranslate=True):
	try:
		if not lang and defaultLanguage == "en":
			lang = "enu"
		if lang:
			locale.setlocale(locale.LC_ALL, lang)
	except locale.Error as err:
		log.error(err)
		msg = _(
			"Metadata and extra tags error. '%s' value was not recognized for lang field." % lang)
		return False, msg
	replacements = getReplacements(lang)
	for toSearch, replaceBy, replaceAlways in replacements:
		if allRepl or (not allRepl and replaceAlways):
			try:
				matches = soup.findAll(
					text=re.compile(r".{0,}%s.{0,}" % toSearch))
				for match in matches:
					parents = [parent.name for parent in match.parents]
					if "code" not in parents and "pre" not in parents:
						if allowBacktranslate:
							tag = "div" if "%toc%" in toSearch else "span"
							newContent = str(match.string).replace(
								toSearch, '<%s class="extratag_%s">%s</%s>' % (tag, toSearch, replaceBy, tag))
							match.string.replaceWith(BeautifulSoup(newContent))
						else:
							match.string.replaceWith(
								match.string.replace(toSearch, replaceBy))
			except (UnicodeEncodeError, UnicodeDecodeError):
				match.replaceWith(match.string.replace(
					toSearch, replaceBy.decode(locale.getlocale()[1])))
	if lang:
		locale.setlocale(locale.LC_ALL, '')
	return True, soup


def applyAutoNumberHeadings(soup, before=""):
	patternHeaders = re.compile(r"h[0-6]")
	matches = soup.findAll(patternHeaders, recursive=True)
	l = []
	previousHeadingLevel = 0
	for match in matches:
		if match.text.strip().startswith(internalAutoNumber):
			match.string.replaceWith(
				match.string.replace(internalAutoNumber, ""))
			continue
		currentHeadingLevel = int(match.name[-1])
		if currentHeadingLevel == previousHeadingLevel:
			l[-1] += 1
		elif currentHeadingLevel < previousHeadingLevel:
			try:
				l = l[0:currentHeadingLevel]
				l[-1] += 1
			except KeyError as err:
				log.error((repr(err), l, previousHeadingLevel,
						   currentHeadingLevel, match.text, d))
				return soup
		else:
			diff = currentHeadingLevel-previousHeadingLevel
			l += [0]*diff
			l[-1] = 1
		current = '.'.join([str(k) for k in l])
		current = re.sub(r"^(0\.)+(.+)$", r"\2", current)
		match.string.replaceWith("%s. %s" % (current, match.string))
		previousHeadingLevel = currentHeadingLevel
	return soup


def getMetadataBlock(metadata, ignore=[]):
	ignore_ = ["HTMLHead", "HTMLHeader", "genMetadata", "detectExtratags"]
	metadata = {k: v for k, v in metadata.items() if ((isinstance(
		v, str) and v) or not isinstance(v, str)) and k not in (ignore + ignore_)}
	dmp = yaml.dump(metadata, encoding="UTF-8", allow_unicode=True,
					explicit_start=True, explicit_end=True)
	return dmp.decode("UTF-8")


def convertToMD(text, metadata, display=True):
	title = metadata["title"]
	dmp = getMetadataBlock(metadata) if metadata["genMetadata"] else ""
	if metadata["detectExtratags"]:
		text = backTranslateExtraTags(text)
	if config.conf["markdownForever"]["markdownEngine"] == "html2markdown":
		convert = html2markdown.convert
	else:
		convert = html2text.html2text
	res = ("%s\n%s" % (dmp, convert(text))).strip()
	if display:
		pre = (title + " - ") if title else title
		ui.browseableMessage(
			res, pre + _("HTML to Markdown conversion"), False)
	else:
		return res


def copyToClipAsHTML(html):
	winClipboard.copy(html, html=True)
	return html == winClipboard.get(html=True)


def translate_back_toc(s, idx=False):
	t = [
		"a1", "b1", "a2", "b2", "a3", "b3", "a4", "b4", "a5", "b5", "a6", "b6"]
	if isinstance(s, tuple):
		out = []
		for e in s:
			if not isinstance(e, int): continue
			out.append(t[e])
		return ','.join(out)
	s = s.replace(' ', '').lower()
	l = s.split(',')
	if idx:
		out = []
		for e in l:
			if not e in t: continue
			out.append(t.index(e))
		return out
	after = set()
	before = set()
	for e in l:
		if e[-1] not in "123456":
			continue
		if e.startswith('b'):
			before.add('h' + e[-1])
		if e.startswith('a'):
			after.add('h' + e[-1])
	return before, after


def add_back_toc(content, before=["h1"], after=["h2"]):
	if not before and not after:
		return content
	soup = BeautifulSoup(content, "html.parser")
	if before:
		matches = soup.find_all(before)
		for m in matches[1:]:
			link_toc_back = soup.new_tag('a')
			link_toc_back["href"] = "#doc-toc"
			link_toc_back.string = _("Back to Table of Contents")
			m.insert_before(link_toc_back)
	if after:
		matches = soup.find_all(after)
		for m in matches:
			link_toc_back = soup.new_tag('a')
			link_toc_back["href"] = "#doc-toc"
			link_toc_back.string = _("Back to Table of Contents")
			m.insert_after(link_toc_back)
	return soup.prettify()

def convertToHTML(text, metadata, save=False, src=False, useTemplateHTML=True, display=True, fp=''):
	toc = metadata["toc"]
	title = metadata["title"]
	lang = metadata["lang"]
	extratags = metadata["extratags"]
	HTMLHeader = metadata["HTMLHeader"]
	HTMLHead = metadata["HTMLHead"]
	res = md2HTML(text, metadata)
	toc_html = None
	if res.toc_html and res.toc_html.count("<li>") > 1:
		toc_html = res.toc_html
	body = str(res)
	del res
	content = BeautifulSoup(body, "html.parser")
	if metadata["autonumber-headings"]:
		if toc_html:
			toc_html = toc_html.replace("<ul>", "<ol>").replace("</ul>", "</ol>")
		content = applyAutoNumberHeadings(content)
	if extratags:
		ok, content = processExtraTags(content, lang=metadata["langd"] if "langd" in metadata.keys(
		) else '', allowBacktranslate=metadata["extratags-back"])
		if not ok:
			return wx.CallAfter(gui.messageBox, content, addonSummary, wx.OK | wx.ICON_ERROR)
	content = str(content.prettify()) if save else str(content)
	if toc_html:
		if metadata["toc-back"]:
			before, after = translate_back_toc(metadata["toc-back"])
			content = add_back_toc(content, before, after)
		if internalTocTag not in content:
			pre = '<h1 id="doc-toc-h1">%s</h1>' % _("Table of contents")
			content = pre + internalTocTag + content
		content = content.replace(internalTocTag, '<nav role="doc-toc" id="doc-toc">%s</nav>' % toc_html)
	else:
		content = content.replace(internalTocTag, '%toc%')
	if useTemplateHTML:
		useTemplateHTML = not re.search("</html>", body, re.IGNORECASE)
	if not title.strip():
		title = _("Markdown to HTML conversion") + \
			(" (%s)" % time.strftime("%X %x"))
	if useTemplateHTML:
		body = content
		content = getHTMLTemplate(metadata["template"])["content"]
		content = content.replace("{lang}", lang, 1)
		content = content.replace("{head}", HTMLHead, 1)
		content = content.replace("{header}", HTMLHeader, 1)
		content = content.replace("{body}", body, 1)
	if save:
		metadata["path"] = realpath(metadata["path"])
		if not os.path.exists(metadata["path"]):
			fp = os.path.dirname(__file__) + r"\\tmp.html"
		if not fp:
			fp = os.path.join(metadata["path"],
							  "%s.html" % metadata["filename"])
		writeFile(fp, content)
		if display:
			os.startfile(realpath(fp))
	else:
		if lang != defaultLanguage:
			content = "<div lang=\"%s\">%s</div>" % (lang, content)
		if display:
			title = f"{title} — %s" % (_("Markdown to HTML conversion (preview)") if not src else _(
				"Markdown to HTML source conversion"))
			if src:
				content = f"<pre>{escapeHTML(content)}</pre>"
			ui.browseableMessage(content, title, True)
		else:
			return content


def getMarkdown2Extras(index=False, extras=None):
	if not extras:
		extras = config.conf["markdownForever"]["markdown2Extras"].split(',')
	if index:
		return tuple([list(EXTRAS.keys()).index(extra) for extra in extras if extra in EXTRAS.keys()])
	return [extra for extra in extras if extra in EXTRAS.keys()]


def getMarkdown2ExtrasFromIndexes(extras):
	keys = list(EXTRAS.keys())
	return [keys[extra] for extra in extras if 0 <= extra < len(keys)]
