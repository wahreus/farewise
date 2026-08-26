const API_BASE_URL = ["localhost", "127.0.0.1"].includes(window.location.hostname)
                      ? "http://127.0.0.1:8000"
                      : "";
const MAX_UPLOAD_BYTES = 2 * 1024 * 1024;

const form = document.querySelector("#analysis-form");
const fileInput = document.querySelector("#journey-file");
const fileName = document.querySelector("#file-name");
const analyseButton = document.querySelector("#analyse-button");
const statusBox = document.querySelector("#status");
const resultsSection = document.querySelector("#results");

fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];

    if (!file) {
        fileName.textContent = "No file selected";
        analyseButton.disabled = true;
        clearStatus();
        return;
    }

    fileName.textContent = file.name;

    const validationError = validateFile(file);
    if (validationError) {
        showStatus(validationError, "error");
        analyseButton.disabled = true;
        return;
    }

    clearStatus();
    analyseButton.disabled = false;
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const file = fileInput.files[0];
    if (!file) {
        showStatus("Choose a TfL journey-history CSV first.", "error");
        return;
    }

    const validationError = validateFile(file);
    if (validationError) {
        showStatus(validationError, "error");
        return;
    }

    setLoading(true);
    resultsSection.hidden = true;

    const body = new FormData();
    body.append("file", file);

    try {
        const response = await fetch(`${API_BASE_URL}/analyses`, {
            method: "POST",
            body,
        });

        const payload = await readResponse(response);

        if (!response.ok) {
            throw new Error(getErrorMessage(payload, response.status));
        }

        renderResults(payload);
        clearStatus();
        resultsSection.hidden = false;
        resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        const message = error instanceof TypeError
            ? "FareWise could not reach the API. Check that the backend is running."
            : error.message;

        showStatus(message, "error");
    } finally {
        setLoading(false);
    }
});

function validateFile(file) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
        return "The selected file must use the .csv extension.";
    }

    if (file.size > MAX_UPLOAD_BYTES) {
        return "The selected CSV must not exceed 2 MiB.";
    }

    return null;
}

async function readResponse(response) {
    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
        return response.json();
    }

    return { detail: await response.text() };
}

function getErrorMessage(payload, statusCode) {
    if (typeof payload?.detail === "string" && payload.detail.trim()) {
        return payload.detail;
    }

    return `FareWise could not complete the analysis (HTTP ${statusCode}).`;
}

function setLoading(isLoading) {
    analyseButton.disabled = isLoading || !fileInput.files[0];
    analyseButton.textContent = isLoading ? "Analysing..." : "Analyse journeys";

    if (isLoading) {
        showStatus("Analysing journey history...", "loading");
    }
}

function showStatus(message, type) {
    statusBox.textContent = message;
    statusBox.className = `status ${type}`;
    statusBox.hidden = false;
}

function clearStatus() {
    statusBox.textContent = "";
    statusBox.className = "status";
    statusBox.hidden = true;
}

function renderResults(result) {
    document.querySelector("#recorded-total").textContent =
        formatCurrency(result.recorded_payg_total);
    document.querySelector("#optimized-total").textContent =
        formatCurrency(result.optimized_total);
    document.querySelector("#saving-total").textContent =
        formatCurrency(result.estimated_saving);

    document.querySelector("#journey-range").textContent =
        `${formatDate(result.journey_start_date)} – ${formatDate(result.journey_end_date)}`;

    document.querySelector("#strategy-badge").textContent =
        result.uses_travelcard ? "Travelcard + PAYG" : "PAYG only";

    renderSelections(result.selections || []);
    renderInputSummary(result.input_summary);
    renderWarnings(result.warnings || []);
}

function renderSelections(selections) {
    const container = document.querySelector("#selections");
    container.replaceChildren();

    if (selections.length === 0) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "No payment selections were returned.";
        container.append(empty);
        return;
    }

    const groupedSelections = groupSelections(selections);

    groupedSelections.forEach((selection) => {
        container.append(createSelection(selection));
    });
}

function groupSelections(selections) {
    const grouped = [];

    selections.forEach((selection) => {
        const previous = grouped[grouped.length - 1];

        if (
            selection.payment_type === "payg" &&
            previous?.payment_type === "payg"
        ) {
            previous.end_date = selection.end_date;
            previous.total_cost =
                Number(previous.total_cost) + Number(selection.total_cost);
            previous.journey_count =
                Number(previous.journey_count) + Number(selection.journey_count);

            return;
        }

        grouped.push({ ...selection });
    });

    return grouped;
}

function createSelection(selection) {
    const article = document.createElement("article");
    article.className = "selection";

    const heading = document.createElement("div");
    const title = document.createElement("div");
    const meta = document.createElement("div");
    const cost = document.createElement("div");
    const detail = document.createElement("div");

    title.className = "selection-title";
    meta.className = "selection-meta";
    cost.className = "selection-cost";
    detail.className = "selection-detail";

    meta.textContent =
        `${formatDate(selection.start_date)} – ${formatDate(selection.end_date)}`;
    cost.textContent = formatCurrency(selection.total_cost);

    if (selection.payment_type === "travelcard") {
        title.textContent = `${selection.product_name}, ${selection.zone_name}`;
        detail.textContent = [
            `Travelcard ${formatCurrency(selection.card_cost)}`,
            `PAYG outside coverage ${formatCurrency(selection.outside_payg_cost)}`,
            `${selection.covered_journey_count} covered journeys`,
            `${selection.uncovered_journey_count} uncovered journeys`,
        ].join(" · ");
    } else {
        title.textContent = "Pay as you go";
        detail.textContent =
            `${selection.journey_count} ${pluralize("journey", selection.journey_count)}`;
    }

    heading.append(title, meta);
    article.append(heading, cost, detail);
    return article;
}

function renderInputSummary(summary) {
    const container = document.querySelector("#input-summary");
    container.replaceChildren();

    if (!summary) {
        addSummaryRow(container, "Summary", "Unavailable");
        return;
    }

    addSummaryRow(container, "Journeys analysed", summary.loaded_journeys);
    addSummaryRow(container, "CSV rows skipped", summary.skipped_rows);
    addSummaryRow(container, "Unsupported modes", summary.unsupported_transport_modes);
    addSummaryRow(container, "Non-journey actions", summary.non_journey_actions);
    addSummaryRow(container, "Unknown stations", summary.unknown_stations);
    addSummaryRow(container, "Invalid charges", summary.invalid_charges);
}

function addSummaryRow(container, label, value) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");

    term.textContent = label;
    description.textContent = value;

    row.append(term, description);
    container.append(row);
}

function renderWarnings(warnings) {
    const panel = document.querySelector("#warnings-panel");
    const list = document.querySelector("#warnings");
    list.replaceChildren();

    if (warnings.length === 0) {
        panel.hidden = true;
        return;
    }

    warnings.forEach((warning) => {
        const item = document.createElement("li");
        item.textContent = warning;
        list.append(item);
    });

    panel.hidden = false;
}

function formatCurrency(value) {
    const amount = Number(value);

    if (!Number.isFinite(amount)) {
        return `£${value}`;
    }

    return new Intl.NumberFormat("en-GB", {
        style: "currency",
        currency: "GBP",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(amount);
}

function formatDate(value) {
    const date = new Date(`${value}T00:00:00`);

    return new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
    }).format(date);
}

function pluralize(word, count) {
    return Number(count) === 1 ? word : `${word}s`;
}
