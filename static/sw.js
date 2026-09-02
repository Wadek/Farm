self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

function showTray(data) {
  const payload = data || {};
  return self.registration.showNotification(payload.title || "Satokori", {
    body: payload.body || "",
    tag: payload.tag || "satokori",
    icon: "/static/icon.svg",
    badge: "/static/icon.svg",
    data: { url: payload.url || "/" },
  });
}

self.addEventListener("push", (event) => {
  let data = { title: "Satokori", body: "", url: "/" };
  if (event.data) {
    try { data = { ...data, ...event.data.json() }; }
    catch { data.body = event.data.text(); }
  }
  event.waitUntil(showTray(data));
});

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type !== "notify") return;
  event.waitUntil(showTray(data));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        client.postMessage({ type: "open", url });
        if ("focus" in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
