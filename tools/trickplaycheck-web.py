#!/usr/bin/env python3
"""Small LAN web UI for the existing trickplay progress checker."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


SCRIPT_PATH = Path(__file__).with_name("check-trickplay-progress.sh")
CONFIG_PATH = Path(
    os.environ.get("TRICKPLAYCHECK_CONFIG", "/var/lib/trickplaycheck/config.json")
)
MAX_REQUEST_BYTES = 16384
RUN_TIMEOUT_SECONDS = 3600
MAX_LIBRARIES = 20
SUGGESTION_LIMIT = 30

run_lock = threading.Lock()
config_lock = threading.RLock()
libraries: list[dict[str, str]] = []

PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#101827">
  <title>Trickplay Check</title>
  <style>
    :root {
      --control-height: clamp(46px, 4vw, 54px);
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #101827;
      color: #edf2fa;
      font-synthesis: none;
      text-rendering: optimizeLegibility;
    }
    * { box-sizing: border-box; }
    body {
      min-width: 320px;
      min-height: 100vh;
      margin: 0;
      background:
        radial-gradient(ellipse at 80% -10%, #284469 0, transparent 38rem),
        #101827;
    }
    main { width: min(1040px, calc(100% - 40px)); margin: 0 auto; padding: clamp(36px, 7vh, 76px) 0; }
    .page-header { margin-bottom: 30px; }
    .eyebrow { display: flex; align-items: center; gap: 9px; color: #8eb9f5; font-size: .74rem; font-weight: 750; letter-spacing: .16em; text-transform: uppercase; }
    .eyebrow::before { width: 8px; height: 8px; border-radius: 50%; background: #62c9a5; box-shadow: 0 0 14px rgb(98 201 165 / 50%); content: ""; }
    h1 { margin: 12px 0 8px; font-size: clamp(2.15rem, 5vw, 3.45rem); letter-spacing: -.05em; line-height: 1.08; }
    .intro { max-width: 620px; margin: 0; color: #aab8cc; line-height: 1.65; }
    .panel {
      margin-top: 22px;
      padding: clamp(20px, 3vw, 30px);
      border: 1px solid #2a3a50;
      border-radius: 20px;
      background: linear-gradient(145deg, rgb(25 38 57 / 98%), rgb(19 29 44 / 98%));
      box-shadow: 0 24px 70px rgb(0 0 0 / 24%), inset 0 1px 0 rgb(255 255 255 / 2%);
    }
    .app-panel { margin-top: 0; }
    .panel-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
    .panel-header h2 { font-size: 1.35rem; letter-spacing: -.025em; }
    .panel-description { margin: 6px 0 0; color: #91a1b8; font-size: .88rem; line-height: 1.5; }
    .controls { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
    label { display: grid; gap: 8px; color: #c7d2e2; font-size: .88rem; font-weight: 650; }
    select, button { min-height: var(--control-height); border: 1px solid #3a4b64; border-radius: 10px; font: inherit; }
    select { width: 100%; height: var(--control-height); min-width: 0; padding: 0 38px 0 13px; color: #edf2fa; background: #111c2b; }
    button {
      padding: 0 20px;
      border-color: #70a9f8;
      color: #0c1a2d;
      background: #8eb9f5;
      font-weight: 750;
      cursor: pointer;
      transition: background .15s ease, transform .15s ease;
    }
    button:hover:not(:disabled) { background: #a8cbfa; transform: translateY(-1px); }
    button:focus-visible, select:focus-visible, input:focus-visible { outline: 3px solid #c0dcff; outline-offset: 3px; }
    button:disabled { cursor: wait; opacity: .7; }
    .checkbox { display: flex; align-self: end; align-items: center; gap: 11px; height: var(--control-height); min-height: var(--control-height); padding: 0 13px; border: 1px solid #3a4b64; border-radius: 10px; background: #111c2b; font-size: clamp(.78rem, .85vw, .9rem); font-weight: 550; line-height: 1.25; }
    .checkbox input { flex: 0 0 auto; width: 18px; height: 18px; margin: 0; accent-color: #8eb9f5; }
    .checkbox[hidden], .panel[hidden] { display: none; }
    .folder-list { display: grid; gap: 12px; margin: 20px 0; }
    .folder-row { display: grid; grid-template-columns: 1fr 1.5fr 1.5fr auto; gap: 10px; align-items: end; padding: 14px; border: 1px solid #29374c; border-radius: 12px; background: #111c2b; }
    .folder-row label { min-width: 0; }
    .folder-row input, .folder-row select { width: 100%; min-width: 0; min-height: 42px; padding: 0 10px; border: 1px solid #3a4b64; border-radius: 9px; color: #edf2fa; background: #101827; font: inherit; }
    .folder-row .remove-folder { min-height: 42px; padding: 0 12px; border-color: #63434b; color: #ffd4d1; background: #38232a; }
    .setup-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
    .setup-actions .secondary, .settings-button { border-color: #3a4b64; color: #d8e0ec; background: #26364b; }
    .settings-button { display: inline-flex; align-items: center; justify-content: center; gap: 9px; min-height: 42px; padding: 0 14px; border-radius: 10px; white-space: nowrap; }
    .settings-button:hover:not(:disabled), .setup-actions .secondary:hover:not(:disabled) { border-color: #617895; background: #30445e; }
    .settings-button svg { width: 17px; height: 17px; }
    .run-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 20px; }
    .run-hint { color: #8191a8; font-size: .82rem; line-height: 1.5; }
    .run-button { min-width: 160px; }
    .message { margin: 18px 0 0; color: #aab8cc; }
    .message.error { color: #ffaaa8; }
    .spinner {
      display: inline-block;
      width: 15px;
      height: 15px;
      margin-right: 8px;
      border: 2px solid #52647d;
      border-top-color: #a8cbfa;
      border-radius: 50%;
      animation: spin .8s linear infinite;
      vertical-align: -3px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .result { margin-top: 28px; padding-top: 24px; border-top: 1px solid #2a3a50; }
    .result[hidden] { display: none; }
    .result-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
    h2 { margin: 0; font-size: 1.3rem; }
    .meta { color: #91a1b8; font-size: .82rem; overflow-wrap: anywhere; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0 16px; }
    .stat { padding: 16px 18px; border: 1px solid #2c3d53; border-radius: 13px; background: #111c2b; }
    .stat-label { color: #91a1b8; font-size: .78rem; }
    .stat-value { display: block; margin-top: 6px; font-size: clamp(1.4rem, 2.5vw, 1.75rem); font-weight: 760; font-variant-numeric: tabular-nums; letter-spacing: -.03em; }
    .progress { height: 9px; overflow: hidden; border-radius: 99px; background: #303e53; }
    .progress > span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #62c9a5, #8eb9f5); transition: width .3s ease; }
    .titles { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: 12px; margin-top: 20px; }
    .title-card { min-width: 0; padding: 16px 17px; border: 1px solid #2c3d53; border-radius: 13px; background: #111c2b; }
    .title-name { overflow-wrap: anywhere; font-weight: 700; }
    .title-counts { display: flex; gap: 14px; margin-top: 7px; color: #aab8cc; font-size: .82rem; }
    .missing-list { margin: 12px 0 0; padding-left: 20px; color: #e5bd82; font-size: .84rem; line-height: 1.5; }
    .missing-list li { margin-top: 5px; overflow-wrap: anywhere; }
    .empty { margin: 20px 0 0; color: #aab8cc; }
    .details { margin-top: 18px; }
    summary { color: #aab8cc; cursor: pointer; font-size: .86rem; }
    pre { overflow: auto; max-height: 320px; padding: 14px; border-radius: 10px; background: #0c1420; color: #c5d0df; font-size: .78rem; white-space: pre-wrap; overflow-wrap: anywhere; }
    footer { margin-top: 18px; color: #718199; font-size: .78rem; line-height: 1.5; }
    @media (max-width: 760px) {
      main { width: min(100% - 32px, 620px); padding: 36px 0 48px; }
      .page-header { margin-bottom: 22px; }
      .panel { margin-top: 16px; border-radius: 16px; }
      .app-panel { margin-top: 0; }
      .panel-header { align-items: flex-start; gap: 12px; margin-bottom: 20px; }
      .panel-header h2 { font-size: 1.2rem; }
      .panel-description { max-width: 38ch; font-size: .84rem; }
      .controls { grid-template-columns: 1fr 1fr; gap: 10px; }
      .library-control { grid-column: 1 / -1; }
      .checkbox { align-self: stretch; padding: 0 11px; }
      .folder-row { grid-template-columns: 1fr 1fr; }
      .folder-path { grid-column: 1 / -1; }
      .folder-row .remove-folder { width: auto; }
      .run-row { align-items: stretch; flex-direction: column-reverse; gap: 10px; }
      .run-button { width: 100%; min-height: 50px; }
      .run-hint { font-size: .78rem; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }
      .stat { padding: 13px; }
      .result-heading { align-items: flex-start; flex-direction: column; gap: 5px; }
      .titles { grid-template-columns: minmax(0, 1fr); }
    }
    @media (max-width: 420px) {
      main { width: calc(100% - 24px); padding-top: 28px; }
      .panel { padding: 16px; }
      .panel-header { flex-direction: row; align-items: center; }
      .panel-header > div { min-width: 0; }
      .panel-header h2 { font-size: 1.08rem; }
      .settings-button { flex: 0 0 auto; min-height: 40px; gap: 6px; padding: 0 10px; }
      .controls { grid-template-columns: minmax(0, 1fr); }
      .library-control { grid-column: auto; }
      .checkbox { align-self: stretch; padding: 0 10px; gap: 8px; }
      .folder-row { grid-template-columns: minmax(0, 1fr); }
      .folder-path { grid-column: auto; }
      .setup-actions { display: grid; grid-template-columns: 1fr; }
      .setup-actions button { width: 100%; }
      .stats { gap: 8px; }
      .stat-label { font-size: .74rem; }
      .meta { font-size: .76rem; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; transition-duration: .01ms !important; }
    }
  </style>
</head>
<body>
  <main>
    <header class="page-header">
      <div class="eyebrow">Media library tools</div>
      <h1>Trickplay Check</h1>
      <p class="intro">Check trickplay image progress for your selected media folders. The scan runs on this server and only reads folders you configure.</p>
    </header>

    <section id="setup-panel" class="panel" aria-labelledby="setup-title" hidden>
      <h2 id="setup-title">Choose folders for Trickplay Check</h2>
      <p class="intro">Add the media folders this service can scan. Start typing an absolute path to see matching directories on the server. Folders are read-only to the checker.</p>
      <form id="setup-form">
        <div id="folder-list" class="folder-list"></div>
        <datalist id="directory-suggestions"></datalist>
        <div class="setup-actions">
          <button id="add-folder" class="secondary" type="button">Add another folder</button>
          <button id="save-folders" type="submit">Save folders</button>
          <button id="cancel-setup" class="secondary" type="button" hidden>Cancel</button>
        </div>
        <p id="setup-message" class="message" role="status" aria-live="polite"></p>
      </form>
    </section>

    <section id="app-panel" class="panel app-panel" aria-label="Run a trickplay check" hidden>
      <div class="panel-header">
        <div>
          <h2>Run a progress scan</h2>
          <p class="panel-description">Choose a library and scan options to check its trickplay coverage.</p>
        </div>
        <button id="settings" class="settings-button" type="button" aria-label="Configure available folders" title="Configure available folders">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"/>
            <path d="m19.4 15 .1.1a1.7 1.7 0 0 1-2.4 2.4l-.1-.1a1.7 1.7 0 0 0-2.9 1.2v.2a1.7 1.7 0 0 1-3.4 0v-.2a1.7 1.7 0 0 0-2.9-1.2l-.1.1a1.7 1.7 0 0 1-2.4-2.4l.1-.1a1.7 1.7 0 0 0-1.2-2.9H4a1.7 1.7 0 0 1 0-3.4h.2a1.7 1.7 0 0 0 1.2-2.9l-.1-.1a1.7 1.7 0 0 1 2.4-2.4l.1.1a1.7 1.7 0 0 0 2.9-1.2V2a1.7 1.7 0 0 1 3.4 0v.2a1.7 1.7 0 0 0 2.9 1.2l.1-.1a1.7 1.7 0 0 1 2.4 2.4l-.1.1a1.7 1.7 0 0 0 1.2 2.9h.2a1.7 1.7 0 0 1 0 3.4h-.2a1.7 1.7 0 0 0-1.2 2.9Z"/>
          </svg>
          <span>Folders</span>
        </button>
      </div>
      <div class="controls">
        <label class="library-control" for="library">Library
          <select id="library"></select>
        </label>
        <label class="checkbox" for="remaining">
          <input id="remaining" type="checkbox">
          Only titles with remaining videos
        </label>
        <label id="missing-option" class="checkbox" for="list-missing" hidden>
          <input id="list-missing" type="checkbox">
          List missing videos
        </label>
      </div>
      <div class="run-row">
        <span class="run-hint">Scans are read-only and can take several minutes for large libraries.</span>
        <button id="run" class="run-button" type="button">Run check</button>
      </div>
      <p id="message" class="message" role="status" aria-live="polite">Choose a library and run a scan.</p>

      <section id="result" class="result" aria-labelledby="result-title" hidden>
        <div class="result-heading">
          <h2 id="result-title">Scan result</h2>
          <span id="meta" class="meta"></span>
        </div>
        <div class="stats" aria-label="Overall progress">
          <div class="stat"><span class="stat-label">Complete</span><strong id="percent" class="stat-value">0%</strong></div>
          <div class="stat"><span class="stat-label">Videos done</span><strong id="done" class="stat-value">0</strong></div>
          <div class="stat"><span class="stat-label">Total videos</span><strong id="total" class="stat-value">0</strong></div>
          <div class="stat"><span class="stat-label">Remaining</span><strong id="left" class="stat-value">0</strong></div>
        </div>
        <div class="progress" role="progressbar" aria-label="Trickplay completion" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
          <span id="progress-fill" style="width: 0%"></span>
        </div>
        <p id="empty" class="empty" hidden></p>
        <div id="titles" class="titles"></div>
        <details id="details" class="details">
          <summary>Show raw script output</summary>
          <pre id="output"></pre>
        </details>
      </section>
    </section>
    <footer>Only folders configured for this service can be scanned.</footer>
  </main>
  <script>
    const runButton = document.querySelector("#run");
    const message = document.querySelector("#message");
    const result = document.querySelector("#result");
    const librarySelect = document.querySelector("#library");
    const missingOption = document.querySelector("#missing-option");
    const missingCheckbox = document.querySelector("#list-missing");
    const setupPanel = document.querySelector("#setup-panel");
    const appPanel = document.querySelector("#app-panel");
    const setupForm = document.querySelector("#setup-form");
    const folderList = document.querySelector("#folder-list");
    const setupMessage = document.querySelector("#setup-message");
    const saveButton = document.querySelector("#save-folders");
    const cancelSetupButton = document.querySelector("#cancel-setup");
    const number = value => new Intl.NumberFormat().format(value);
    let configuredLibraries = [];

    function updateMissingOption() {
      const library = configuredLibraries.find(item => item.id === librarySelect.value);
      const supportsMissingList = library?.kind === "shows";
      missingOption.hidden = !supportsMissingList;
      if (!supportsMissingList) missingCheckbox.checked = false;
    }

    function showConfiguration(libraries, editing) {
      setupPanel.hidden = false;
      appPanel.hidden = true;
      setupMessage.className = "message";
      setupMessage.textContent = "";
      document.querySelector("#setup-title").textContent = editing
        ? "Configure available folders"
        : "Choose folders for Trickplay Check";
      cancelSetupButton.hidden = !editing;
      saveButton.textContent = editing ? "Save changes" : "Save folders";
      folderList.replaceChildren();
      (libraries.length ? libraries : [{}]).forEach(addFolderRow);
    }

    function addFolderRow(library = {}) {
      const row = document.createElement("div");
      row.className = "folder-row";
      row.innerHTML = `
        <label>Display name
          <input name="name" type="text" maxlength="80" placeholder="TV Shows" value="">
        </label>
        <label>Folder path
          <input name="path" type="text" list="directory-suggestions" autocomplete="off"
                 placeholder="/media/synology_media/shows" required>
        </label>
        <label>Content type
          <select name="kind">
            <option value="shows">TV shows</option>
            <option value="library">Movies / other videos</option>
          </select>
        </label>
        <button class="remove-folder" type="button" aria-label="Remove folder">Remove</button>`;
      row.querySelector('[name="name"]').value = library.name || "";
      row.querySelector('[name="path"]').value = library.path || "";
      row.querySelector('[name="kind"]').value = library.kind || "shows";
      row.querySelector(".remove-folder").addEventListener("click", () => row.remove());

      const pathInput = row.querySelector('[name="path"]');
      let suggestionTimer;
      pathInput.addEventListener("input", () => {
        window.clearTimeout(suggestionTimer);
        suggestionTimer = window.setTimeout(async () => {
          if (!pathInput.value.startsWith("/") && !pathInput.value.startsWith("~")) return;
          try {
            const response = await fetch(`/api/suggest?path=${encodeURIComponent(pathInput.value)}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Could not load folder suggestions.");
            const suggestions = document.querySelector("#directory-suggestions");
            suggestions.replaceChildren(...data.suggestions.map(path => {
              const option = document.createElement("option");
              option.value = path;
              return option;
            }));
          } catch (error) {
            setupMessage.className = "message error";
            setupMessage.textContent = `${error.message || "Could not load folder suggestions."} You can still enter a path manually.`;
          }
        }, 180);
      });
      folderList.append(row);
    }

    function showApplication(libraries) {
      configuredLibraries = libraries;
      librarySelect.replaceChildren(...libraries.map(library => {
        const option = document.createElement("option");
        option.value = library.id;
        option.textContent = library.name;
        return option;
      }));
      setupPanel.hidden = true;
      appPanel.hidden = false;
      updateMissingOption();
    }

    async function loadConfiguration() {
      const response = await fetch("/api/config");
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not load folder configuration.");
      if (data.libraries.length) showApplication(data.libraries);
      else showConfiguration([], false);
    }

    function addText(parent, tag, className, text) {
      const element = document.createElement(tag);
      element.className = className;
      element.textContent = text;
      parent.append(element);
      return element;
    }

    function render(data) {
      const stats = data.stats;
      document.querySelector("#result-title").textContent = `${data.library} trickplay progress`;
      document.querySelector("#meta").textContent = `${data.directory} · ${data.duration_seconds}s · ${new Date(data.finished_at).toLocaleString()}`;
      document.querySelector("#percent").textContent = `${stats.percent}%`;
      document.querySelector("#done").textContent = number(stats.done);
      document.querySelector("#total").textContent = number(stats.total);
      document.querySelector("#left").textContent = number(stats.left);
      document.querySelector(".progress").setAttribute("aria-valuenow", stats.percent);
      document.querySelector("#progress-fill").style.width = `${stats.percent}%`;

      const titles = document.querySelector("#titles");
      titles.replaceChildren();
      data.titles.forEach(title => {
        const card = document.createElement("article");
        card.className = "title-card";
        addText(card, "div", "title-name", title.name);
        const counts = document.createElement("div");
        counts.className = "title-counts";
        counts.textContent = `Done ${number(title.done)} · Total ${number(title.total)} · Remaining ${number(title.remaining)}`;
        card.append(counts);
        if (title.missing.length > 0) {
          addText(card, "div", "title-counts", "Missing episodes");
          const missingList = document.createElement("ul");
          missingList.className = "missing-list";
          title.missing.forEach(filename => addText(missingList, "li", "", filename));
          card.append(missingList);
        }
        titles.append(card);
      });

      const empty = document.querySelector("#empty");
      empty.hidden = data.titles.length !== 0;
      empty.textContent = stats.total === 0
        ? "No video files were found in this library."
        : "No titles have remaining videos.";
      document.querySelector("#output").textContent = data.output;
      document.querySelector("#details").open = false;
      result.hidden = false;
    }

    runButton.addEventListener("click", async () => {
      runButton.disabled = true;
      result.hidden = true;
      message.className = "message";
      message.innerHTML = '<span class="spinner" aria-hidden="true"></span>Scanning the library. Large libraries may take several minutes…';
      try {
        const response = await fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            library: document.querySelector("#library").value,
            remaining_only: document.querySelector("#remaining").checked,
            list_missing: missingCheckbox.checked
          })
        });
        const data = await response.json();
        if (!response.ok) {
          const error = new Error(data.error || `Request failed (${response.status})`);
          error.details = data.details;
          throw error;
        }
        render(data);
        message.textContent = "Scan complete.";
      } catch (error) {
        message.className = "message error";
        message.textContent = error.message || "The scan failed.";
        if (error.details) {
          document.querySelector("#output").textContent = error.details;
          document.querySelector("#details").open = true;
          result.hidden = false;
        }
      } finally {
        runButton.disabled = false;
      }
    });

    librarySelect.addEventListener("change", updateMissingOption);
    document.querySelector("#add-folder").addEventListener("click", () => addFolderRow());
    document.querySelector("#settings").addEventListener("click", () => {
      showConfiguration(configuredLibraries, true);
    });
    cancelSetupButton.addEventListener("click", () => showApplication(configuredLibraries));
    setupForm.addEventListener("submit", async event => {
      event.preventDefault();
      saveButton.disabled = true;
      setupMessage.className = "message";
      setupMessage.textContent = "Checking folders and saving configuration…";
      const submittedLibraries = [...folderList.querySelectorAll(".folder-row")].map(row => ({
        name: row.querySelector('[name="name"]').value.trim(),
        path: row.querySelector('[name="path"]').value.trim(),
        kind: row.querySelector('[name="kind"]').value
      }));
      try {
        const response = await fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ libraries: submittedLibraries })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not save folders.");
        showApplication(data.libraries);
        message.className = "message";
        message.textContent = "Folder configuration saved.";
      } catch (error) {
        setupMessage.className = "message error";
        setupMessage.textContent = error.message || "Could not save folders.";
      } finally {
        saveButton.disabled = false;
      }
    });
    loadConfiguration().catch(error => {
      setupPanel.hidden = false;
      setupMessage.className = "message error";
      setupMessage.textContent = error.message || "Could not load folder configuration.";
    });
  </script>
</body>
</html>
"""

TITLE_RE = re.compile(r"^Title: (.*)$", re.MULTILINE)
COUNT_RE = re.compile(r"^  (Done|Total|Remaining):\s+(\d+)$", re.MULTILINE)
MISSING_RE = re.compile(r"^    - (.*)$", re.MULTILINE)
OVERALL_RE = re.compile(
    r"^Overall: (\d+)/(\d+) done \((\d+)%\), (\d+) left\.$", re.MULTILINE
)


def parse_output(output: str) -> tuple[list[dict[str, object]], dict[str, int]]:
    titles: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line in output.splitlines():
        title_match = TITLE_RE.match(line)
        if title_match:
            current = {
                "name": title_match.group(1),
                "done": 0,
                "total": 0,
                "remaining": 0,
                "missing": [],
            }
            titles.append(current)
            continue

        count_match = COUNT_RE.match(line)
        if current is not None and count_match:
            key = count_match.group(1).lower()
            current[key] = int(count_match.group(2))
            continue

        missing_match = MISSING_RE.match(line)
        if current is not None and missing_match:
            missing = current["missing"]
            if isinstance(missing, list):
                missing.append(missing_match.group(1))

    overall_match = OVERALL_RE.search(output)
    if overall_match:
        stats = {
            "done": int(overall_match.group(1)),
            "total": int(overall_match.group(2)),
            "percent": int(overall_match.group(3)),
            "left": int(overall_match.group(4)),
        }
    else:
        stats = {"done": 0, "total": 0, "percent": 0, "left": 0}

    return titles, stats


def load_configuration() -> list[dict[str, str]]:
    if not CONFIG_PATH.exists():
        return []

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Could not read folder configuration at {CONFIG_PATH}: {error}"
        ) from error

    if not isinstance(config, dict) or not isinstance(config.get("libraries"), list):
        raise RuntimeError(f"Folder configuration at {CONFIG_PATH} has an invalid format.")

    loaded: list[dict[str, str]] = []
    for library in config["libraries"]:
        if (
            not isinstance(library, dict)
            or not all(
                isinstance(library.get(key), str)
                for key in ("id", "name", "path", "kind")
            )
            or library["kind"] not in ("shows", "library")
            or not Path(library["path"]).is_absolute()
        ):
            raise RuntimeError(
                f"Folder configuration at {CONFIG_PATH} has an invalid library entry."
            )
        loaded.append(
            {
                "id": library["id"],
                "name": library["name"],
                "path": library["path"],
                "kind": library["kind"],
            }
        )
    if len(loaded) > MAX_LIBRARIES:
        raise RuntimeError(f"Folder configuration at {CONFIG_PATH} has too many libraries.")
    return loaded


def save_configuration(configured: list[dict[str, str]]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG_PATH.parent,
            prefix=".config-",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump({"libraries": configured}, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, CONFIG_PATH)
    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def validate_configuration(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("libraries"), list):
        raise ValueError("Provide a libraries list.")
    submitted = payload["libraries"]
    if not 1 <= len(submitted) <= MAX_LIBRARIES:
        raise ValueError(f"Add between 1 and {MAX_LIBRARIES} folders.")

    configured: list[dict[str, str]] = []
    names: set[str] = set()
    paths: set[str] = set()
    for entry in submitted:
        if not isinstance(entry, dict):
            raise ValueError("Each folder entry must be an object.")
        name = entry.get("name", "")
        raw_path = entry.get("path")
        kind = entry.get("kind")
        if (
            not isinstance(name, str)
            or not isinstance(raw_path, str)
            or not raw_path.strip()
            or not isinstance(kind, str)
            or kind not in ("shows", "library")
        ):
            raise ValueError("Each folder needs a name, an absolute path, and a content type.")
        raw_path = raw_path.strip()
        name = name.strip() or Path(raw_path).name or raw_path
        if len(name) > 80 or any(ord(character) < 32 for character in name):
            raise ValueError(
                "Folder names must be at most 80 characters and contain no control characters."
            )
        if name.casefold() in names:
            raise ValueError(f"Folder names must be unique: {name}")
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            raise ValueError(f"Folder paths must be absolute: {raw_path}")
        try:
            resolved_path = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ValueError(f"Could not resolve folder path {raw_path}: {error}") from error
        if not resolved_path.is_dir():
            raise ValueError(f"Folder path is not a directory: {resolved_path}")
        if not os.access(resolved_path, os.R_OK | os.X_OK):
            raise ValueError(f"Service user cannot read folder: {resolved_path}")
        path_string = str(resolved_path)
        if path_string in paths:
            raise ValueError(f"Folder paths must be unique: {path_string}")
        names.add(name.casefold())
        paths.add(path_string)
        configured.append(
            {
                "id": uuid.uuid4().hex,
                "name": name,
                "path": path_string,
                "kind": kind,
            }
        )
    return configured


def suggest_directories(raw_path: str) -> list[str]:
    if not raw_path:
        parent = Path("/")
        prefix = ""
    else:
        expanded_path = Path(raw_path).expanduser()
        if not expanded_path.is_absolute():
            raise ValueError("Start with an absolute path, such as /media.")
        if raw_path.endswith("/"):
            parent = expanded_path
            prefix = ""
        else:
            parent = expanded_path.parent
            prefix = expanded_path.name.casefold()

    if not parent.is_dir():
        raise ValueError(f"Directory does not exist: {parent}")
    if not os.access(parent, os.R_OK | os.X_OK):
        raise PermissionError(f"Cannot list folders in {parent}.")

    suggestions: list[str] = []
    with os.scandir(parent) as entries:
        for entry in entries:
            if not entry.name.casefold().startswith(prefix):
                continue
            try:
                if entry.is_dir(follow_symlinks=True):
                    suggestions.append(str((parent / entry.name).resolve()))
            except OSError:
                continue
    suggestions.sort(key=str.casefold)
    return suggestions[:SUGGESTION_LIMIT]


class TrickplayHandler(BaseHTTPRequestHandler):
    server_version = "TrickplayCheck"
    sys_version = ""

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'; connect-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        super().end_headers()

    def send_json(self, status: int, body: dict[str, object]) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        request_path = urlsplit(self.path)
        if request_path.path == "/api/config":
            with config_lock:
                current_libraries = [dict(item) for item in libraries]
            self.send_json(200, {"libraries": current_libraries})
            return
        if request_path.path == "/api/suggest":
            query = parse_qs(request_path.query)
            raw_path = query.get("path", [""])[0]
            try:
                suggestions = suggest_directories(raw_path)
            except PermissionError as error:
                self.send_json(403, {"error": str(error)})
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            except OSError as error:
                self.send_json(500, {"error": f"Could not list folder suggestions: {error}"})
            else:
                self.send_json(200, {"suggestions": suggestions})
            return
        if request_path.path != "/":
            self.send_error(404, "Not found")
            return

        payload = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        request_path = urlsplit(self.path).path
        if request_path not in ("/api/run", "/api/config"):
            self.send_json(404, {"error": "Not found"})
            return

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if content_type != "application/json":
            self.send_json(415, {"error": "Content-Type must be application/json"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.send_json(400, {"error": "A valid Content-Length header is required"})
            return
        if content_length < 0 or content_length > MAX_REQUEST_BYTES:
            self.send_json(413, {"error": "Request body is too large"})
            return

        try:
            request = json.loads(self.rfile.read(content_length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "Request body must be valid JSON"})
            return

        if not isinstance(request, dict):
            self.send_json(400, {"error": "Request body must be a JSON object"})
            return
        if request_path == "/api/config":
            try:
                configured = validate_configuration(request)
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
                return
            try:
                with config_lock:
                    save_configuration(configured)
                    libraries[:] = configured
            except OSError as error:
                self.send_json(500, {"error": f"Could not save folder configuration: {error}"})
                return
            self.send_json(200, {"libraries": configured})
            return

        with config_lock:
            configured_libraries = [dict(item) for item in libraries]

        library_key = request.get("library")
        remaining_only = request.get("remaining_only", False)
        list_missing = request.get("list_missing", False)
        if (
            not isinstance(library_key, str)
            or not any(item["id"] == library_key for item in configured_libraries)
            or type(remaining_only) is not bool
            or type(list_missing) is not bool
            or (
                list_missing
                and next(
                    (
                        item["kind"]
                        for item in configured_libraries
                        if item["id"] == library_key
                    ),
                    None,
                )
                != "shows"
            )
        ):
            self.send_json(400, {"error": "Choose a valid library and scan option"})
            return

        if not run_lock.acquire(blocking=False):
            self.send_json(409, {"error": "A trickplay scan is already running"})
            return

        try:
            selected_library = next(
                item for item in configured_libraries if item["id"] == library_key
            )
            library_name = selected_library["name"]
            media_path = Path(selected_library["path"])
            if not media_path.is_dir():
                self.send_json(
                    503,
                    {"error": f"Library directory is not available: {media_path}"},
                )
                return
            if not SCRIPT_PATH.is_file():
                self.send_json(500, {"error": f"Checker script is missing: {SCRIPT_PATH}"})
                return

            command = ["bash", str(SCRIPT_PATH)]
            if remaining_only:
                command.append("--remaining")
            if list_missing:
                command.append("--list-missing")
            command.append(str(media_path))
            started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            start_time = time.monotonic()

            try:
                process = subprocess.Popen(
                    command,
                    cwd=SCRIPT_PATH.parent.parent,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    start_new_session=True,
                )
            except OSError as error:
                self.send_json(500, {"error": f"Could not start the checker: {error}"})
                return

            try:
                stdout, stderr = process.communicate(timeout=RUN_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
                details = "\n".join(part for part in (stdout, stderr) if part)
                self.send_json(
                    504,
                    {
                        "error": "The scan exceeded its one-hour time limit.",
                        "details": details[-20000:],
                    },
                )
                return

            duration = round(time.monotonic() - start_time, 1)
            if process.returncode != 0:
                details = "\n".join(part for part in (stdout, stderr) if part)
                self.send_json(
                    500,
                    {
                        "error": f"The checker exited with status {process.returncode}.",
                        "details": details[-20000:],
                    },
                )
                return

            output = stdout
            titles, stats = parse_output(output)
            self.send_json(
                200,
                {
                    "library": library_name,
                    "directory": str(media_path),
                    "started_at": started_at,
                    "finished_at": datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    ),
                    "duration_seconds": duration,
                    "stats": stats,
                    "titles": titles,
                    "output": output,
                },
            )
        finally:
            run_lock.release()

def main() -> None:
    global libraries
    parser = argparse.ArgumentParser(description="Serve a LAN trickplay progress page")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    libraries = load_configuration()
    server = ThreadingHTTPServer((args.host, args.port), TrickplayHandler)
    print(f"Trickplay check page listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
