import json

import plotly.io as pio
import werkzeug
from tensorboard import plugin_util
from tensorboard.backend import http_util
from tensorboard.data import provider
from tensorboard.plugins import base_plugin
from werkzeug import wrappers

from . import metadata

_INDEX_JS = r"""
function localUrl(path) {
  return new URL(path, import.meta.url).href;
}

function loadPlotly() {
  if (window.Plotly) {
    return Promise.resolve(window.Plotly);
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");

    // IMPORTANT:
    // This is served by the TensorBoard plugin backend, not by cdn.plot.ly.
    script.src = localUrl("./plotly.min.js");

    script.onload = () => resolve(window.Plotly);
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);

  for (const [key, value] of Object.entries(attrs)) {
    if (key === "style") {
      Object.assign(node.style, value);
    } else if (key === "className") {
      node.className = value;
    } else {
      node.setAttribute(key, value);
    }
  }

  for (const child of children) {
    if (typeof child === "string") {
      node.appendChild(document.createTextNode(child));
    } else {
      node.appendChild(child);
    }
  }

  return node;
}

async function fetchJson(path, params = {}) {
  const url = new URL(path, import.meta.url);

  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return await response.json();
}

export async function render(context) {
  const Plotly = await loadPlotly();

  const root = context.container || document.body;
  root.innerHTML = "";

  const style = el("style", {}, [`
    body {
      font-family: Roboto, Arial, sans-serif;
      margin: 0;
      color: #333;
      background: #fafafa;
    }

    .tbp-page {
      padding: 24px;
    }

    .tbp-toolbar {
      display: flex;
      gap: 16px;
      align-items: center;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }

    .tbp-field {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 12px;
      color: #666;
    }

    .tbp-field select {
      min-width: 180px;
      padding: 6px;
      font-size: 14px;
    }

    .tbp-card {
      background: white;
      border-radius: 4px;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.20);
      padding: 16px;
      max-width: 900px;
    }

    .tbp-title {
      font-size: 15px;
      font-weight: 500;
      margin-bottom: 12px;
    }

    .tbp-plot {
      width: 100%;
      height: 650px;
    }

    .tbp-error {
      color: #b00020;
      white-space: pre-wrap;
    }
  `]);

  document.head.appendChild(style);

  const runSelect = el("select");
  const tagSelect = el("select");
  const stepSelect = el("select");

  const title = el("div", { className: "tbp-title" }, ["Plotly"]);
  const plotDiv = el("div", { className: "tbp-plot" });
  const errorDiv = el("div", { className: "tbp-error" });

  const page = el("div", { className: "tbp-page" }, [
    el("div", { className: "tbp-toolbar" }, [
      el("label", { className: "tbp-field" }, ["Run", runSelect]),
      el("label", { className: "tbp-field" }, ["Tag", tagSelect]),
      el("label", { className: "tbp-field" }, ["Step", stepSelect]),
    ]),
    el("div", { className: "tbp-card" }, [
      title,
      errorDiv,
      plotDiv,
    ]),
  ]);

  root.appendChild(page);

  let tagsByRun = {};
  let currentEvents = [];

  function setError(err) {
    errorDiv.textContent = err ? String(err.stack || err.message || err) : "";
  }

  function fillSelect(select, values) {
    select.innerHTML = "";

    for (const value of values) {
      const option = el("option", { value }, [String(value)]);
      select.appendChild(option);
    }
  }

  async function loadTags() {
    tagsByRun = await fetchJson("./tags");

    const runs = Object.keys(tagsByRun).sort();
    fillSelect(runSelect, runs);

    if (runs.length === 0) {
      title.textContent = "No Plotly summaries found";
      return;
    }

    await loadTagsForRun();
  }

  async function loadTagsForRun() {
    const run = runSelect.value;
    const tags = Object.keys(tagsByRun[run] || {}).sort();

    fillSelect(tagSelect, tags);

    if (tags.length > 0) {
      await loadEvents();
    }
  }

  async function loadEvents() {
    setError(null);

    const run = runSelect.value;
    const tag = tagSelect.value;

    title.textContent = tag || "Plotly";

    if (!run || !tag) {
      return;
    }

    currentEvents = await fetchJson("./plots", { run, tag });

    const steps = currentEvents.map((event) => `${event.step}`);
    fillSelect(stepSelect, steps);

    if (currentEvents.length > 0) {
      stepSelect.value = String(currentEvents[currentEvents.length - 1].step);
      await drawCurrentStep();
    }
  }

  async function drawCurrentStep() {
    setError(null);

    const selectedStep = Number(stepSelect.value);
    const event =
      currentEvents.find((e) => Number(e.step) === selectedStep) ||
      currentEvents[currentEvents.length - 1];

    if (!event) {
      return;
    }

    const fig = event.figure || {};
    const data = fig.data || [];
    const layout = fig.layout || {};
    const config = Object.assign({ responsive: true }, fig.config || {});

    title.textContent = `${tagSelect.value} — step ${event.step}`;

    layout.autosize = true;

    await Plotly.react(plotDiv, data, layout, config);
  }

  runSelect.addEventListener("change", () => {
    loadTagsForRun().catch(setError);
  });

  tagSelect.addEventListener("change", () => {
    loadEvents().catch(setError);
  });

  stepSelect.addEventListener("change", () => {
    drawCurrentStep().catch(setError);
  });

  try {
    await loadTags();
  } catch (err) {
    setError(err);
  }
}
"""


class PlotlyPlugin(base_plugin.TBPlugin):
    plugin_name = metadata.PLUGIN_NAME

    def __init__(self, context):
        self.data_provider = context.data_provider
        self._plotly_js = None

    def is_active(self):
        return True

    def frontend_metadata(self):
        return base_plugin.FrontendMetadata(
            es_module_path="/index.js",
            tab_name="Plotly",
        )

    def get_plugin_apps(self):
        return {
            "/index.js": self._serve_js,
            "/plotly.min.js": self._serve_plotly_js,
            "/tags": self._serve_tags,
            "/plots": self._serve_plots,
        }

    @wrappers.Request.application
    def _serve_js(self, request):
        return http_util.Respond(
            request,
            _INDEX_JS,
            "application/javascript",
        )

    @wrappers.Request.application
    def _serve_plotly_js(self, request):
        # plotly.io.get_plotlyjs() returns the bundled Plotly.js source
        # from the installed Python plotly package. No CDN is contacted.
        if self._plotly_js is None:
            self._plotly_js = pio.get_plotlyjs()

        return http_util.Respond(
            request,
            self._plotly_js,
            "application/javascript",
        )

    @wrappers.Request.application
    def _serve_tags(self, request):
        ctx = plugin_util.context(request.environ)
        experiment = plugin_util.experiment_id(request.environ)

        mapping = self.data_provider.list_tensors(
            ctx,
            experiment_id=experiment,
            plugin_name=metadata.PLUGIN_NAME,
        )

        result = {}

        for run, tag_to_content in mapping.items():
            result[run] = {}
            for tag in tag_to_content.keys():
                result[run][tag] = {}

        return http_util.Respond(
            request,
            json.dumps(result),
            "application/json",
        )

    @wrappers.Request.application
    def _serve_plots(self, request):
        run = request.args.get("run")
        tag = request.args.get("tag")

        if run is None or tag is None:
            raise werkzeug.exceptions.BadRequest("Must specify run and tag")

        ctx = plugin_util.context(request.environ)
        experiment = plugin_util.experiment_id(request.environ)

        read_result = self.data_provider.read_tensors(
            ctx,
            experiment_id=experiment,
            plugin_name=metadata.PLUGIN_NAME,
            downsample=1000,
            run_tag_filter=provider.RunTagFilter(
                runs=[run],
                tags=[tag],
            ),
        )

        events = read_result.get(run, {}).get(tag, [])

        result = []

        for event in events:
            payload = _decode_string_tensor(event.numpy)

            result.append(
                {
                    "wall_time": event.wall_time,
                    "step": event.step,
                    "figure": json.loads(payload),
                }
            )

        return http_util.Respond(
            request,
            json.dumps(result),
            "application/json",
        )


def _decode_string_tensor(value):
    if hasattr(value, "item"):
        value = value.item()

    if isinstance(value, bytes):
        return value.decode("utf-8")

    if isinstance(value, str):
        return value

    try:
        value = value.reshape(()).item()

        if isinstance(value, bytes):
            return value.decode("utf-8")

        if isinstance(value, str):
            return value
    except Exception:
        pass

    raise TypeError(f"Could not decode string tensor of type {type(value)}")
