"use strict";

const url = new URL(window.location.href);
const fragment = new URLSearchParams(url.hash.slice(1));
const sessionId = fragment.get("session_id") || url.searchParams.get("session_id");
const storageKey = "maybloom-eat-shop-order";
if (sessionId) {
  sessionStorage.setItem(storageKey, sessionId);
  history.replaceState(null, "", url.pathname);
}
const checkout = sessionId || sessionStorage.getItem(storageKey);
const statusText = document.getElementById("status");
const downloadButton = document.getElementById("download");

function request(path) {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: checkout }),
    cache: "no-store",
  });
}

async function checkPayment(attempt = 0) {
  if (!checkout) {
    statusText.textContent = "请从结账完成页打开此页。 Open this page from your Stripe checkout.";
    return;
  }
  try {
    const response = await request("/status");
    if (response.ok && (await response.json()).ready) {
      statusText.textContent = "付款已确认。 Payment confirmed.";
      downloadButton.hidden = false;
      return;
    }
  } catch {
    // Retry briefly when the buyer reconnects or the webhook is still in flight.
  }
  if (attempt < 19) {
    window.setTimeout(() => checkPayment(attempt + 1), 3000);
  } else {
    statusText.textContent = "付款尚待确认。稍后刷新此页，或联络我们。 Payment pending. Refresh this page later or contact us.";
  }
}

downloadButton.addEventListener("click", async () => {
  downloadButton.disabled = true;
  try {
    const response = await request("/download");
    if (!response.ok) throw new Error("Download unavailable");
    const downloadUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = "MayBloom-Eat-and-Shop-Smart-Bundle.pdf";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 60000);
  } catch {
    statusText.textContent = "暂时无法下载，请再试一次。 Download unavailable. Please try again.";
  } finally {
    downloadButton.disabled = false;
  }
});

checkPayment();
