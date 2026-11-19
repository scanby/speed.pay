/* ES5 compatible client script for Windows 7 (Chrome 70+ / IE11 / Firefox) */
(function () {
  "use strict";

  var state = {
    user: null,
    requiresSetup: false,
    socket: null,
    audioUnlocked: false,
    heartbeatTimer: null,
    reconnectAttempts: 0,
    lastPongAt: 0
  };

  function el(id) {
    return document.getElementById(id);
  }

  function formatCOP(val) {
    var num = parseFloat(val || 0);
    return "$" + num.toLocaleString("es-CO", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  }

  function apiRequest(method, url, body, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.withCredentials = true;
    if (body !== null) {
      xhr.setRequestHeader("Content-Type", "application/json");
    }
    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4) {
        var parsed = null;
        try {
          parsed = xhr.responseText ? JSON.parse(xhr.responseText) : null;
        } catch (e) {
          parsed = null;
        }
        callback(xhr.status, parsed);
      }
    };
    xhr.send(body !== null ? JSON.stringify(body) : null);
  }

  function setNetworkStatus(isOnline, detailText) {
    var dot = el("heartbeat-dot");
    var label = el("heartbeat-label");
    if (isOnline) {
      dot.className = "status-dot status-online";
      label.textContent = "En línea" + (detailText ? " · " + detailText : "");
      label.style.color = "#15803d";
    } else {
      dot.className = "status-dot status-offline";
      label.textContent = "Desconectado del servidor" + (detailText ? " · " + detailText : "");
      label.style.color = "#b91c1c";
    }
  }

  function startHeartbeatAndSocket() {
    if (state.socket) {
      return;
    }

    var socket = window.io({
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 30000
    });
    state.socket = socket;

    socket.on("connect", function () {
      state.reconnectAttempts = 0;
      state.lastPongAt = Date.now();
      setNetworkStatus(true, "Heartbeat 5s");
    });

    socket.on("disconnect", function () {
      state.reconnectAttempts += 1;
      setNetworkStatus(false, "Reintentando conexión...");
    });

    socket.on("connect_error", function () {
      setNetworkStatus(false, "Sin respuesta del servidor LAN");
    });

    socket.on("new_deposit", function (tx) {
      handleIncomingDeposit(tx);
    });

    state.heartbeatTimer = setInterval(function () {
      if (!socket.connected) {
        setNetworkStatus(false, "Reconectando...");
        return;
      }
      socket.emit("heartbeat_ping", { ts: Date.now() }, function (ack) {
        if (ack && ack.status === "ok") {
          state.lastPongAt = Date.now();
          setNetworkStatus(true, "Heartbeat OK");
        }
      });
      if (Date.now() - state.lastPongAt > 12000) {
        setNetworkStatus(false, "Timeout de latido");
      }
    }, 5000);
  }

  function playAudioAlert(audioUrl) {
    if (!audioUrl) {
      return;
    }
    var player = el("pos-audio-player");
    player.src = audioUrl + "?t=" + Date.now();
    var promise = player.play();
    if (promise && typeof promise.catch === "function") {
      promise.catch(function () {
        /* En Windows 7, el agente Python nativo garantiza reproducción aunque el navegador bloquee autoplay */
      });
    }
  }

  function handleIncomingDeposit(tx) {
    var banner = el("live-alert-banner");
    banner.classList.remove("hidden");
    el("live-alert-amount").textContent = formatCOP(tx.amount_cop);
    el("live-alert-meta").textContent =
      tx.account_alias + " · De: " + tx.sender_name + " · " + tx.tts_phrase;

    playAudioAlert(tx.audio_url);
    loadTodayDeposits();
  }

  function loadTodayDeposits() {
    apiRequest("GET", "/api/deposits/today", null, function (status, data) {
      if (status !== 200 || !data) {
        return;
      }
      el("today-date-label").textContent = data.date;
      if (state.user && state.user.role === "ADMIN") {
        el("kpi-today-count").textContent = String(data.count);
        el("kpi-today-total").textContent = formatCOP(data.total_cop);
      }
      var tbody = el("today-tbody");
      tbody.innerHTML = "";
      if (!data.items || data.items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-cell">Sin movimientos registrados hoy.</td></tr>';
        return;
      }
      for (var i = 0; i < data.items.length; i++) {
        var item = data.items[i];
        var tr = document.createElement("tr");
        var timeStr = item.captured_at.slice(11, 19);
        tr.innerHTML =
          "<td>" + timeStr + "</td>" +
          "<td>" + item.account_alias + "</td>" +
          "<td>" + item.sender_name + "</td>" +
          '<td class="text-right">' + formatCOP(item.amount_cop) + "</td>";
        tbody.appendChild(tr);
      }
    });
  }

  function loadAdminPanel() {
    apiRequest("GET", "/api/admin/config", null, function (status, cfg) {
      if (status === 200 && cfg) {
        el("cfg-ip").textContent = cfg.lan_ip;
        el("cfg-port").textContent = String(cfg.server_port);
        el("cfg-token").textContent = cfg.api_token;
      }
    });
    apiRequest("GET", "/api/admin/config/qr", null, function (status, qr) {
      if (status === 200 && qr) {
        el("qr-image").src = qr.qr_image_base64;
      }
    });
    apiRequest("GET", "/api/admin/users", null, function (status, users) {
      if (status === 200 && users) {
        var list = el("users-list");
        list.innerHTML = "";
        for (var i = 0; i < users.length; i++) {
          var li = document.createElement("li");
          li.textContent = users[i].username + " (" + users[i].role + ") - " + users[i].full_name;
          list.appendChild(li);
        }
      }
    });
    apiRequest("GET", "/api/admin/accounts", null, function (status, accs) {
      if (status === 200 && accs) {
        var list = el("accounts-list");
        list.innerHTML = "";
        for (var i = 0; i < accs.length; i++) {
          var li = document.createElement("li");
          li.textContent = accs[i].alias + " · " + accs[i].phone_number + " (" + accs[i].device_label + ")";
          list.appendChild(li);
        }
      }
    });
  }

  function renderAuthenticatedView(user) {
    state.user = user;
    el("view-auth").classList.add("hidden");
    el("view-pos").classList.remove("hidden");
    el("btn-logout").classList.remove("hidden");
    el("session-user-label").textContent = user.full_name + " (" + user.role + ")";

    var adminEls = document.querySelectorAll(".admin-only");
    for (var i = 0; i < adminEls.length; i++) {
      if (user.role === "ADMIN") {
        adminEls[i].classList.remove("hidden");
      } else {
        adminEls[i].classList.add("hidden");
      }
    }

    startHeartbeatAndSocket();
    loadTodayDeposits();
    if (user.role === "ADMIN") {
      loadAdminPanel();
    }
  }

  function checkSessionOrSetup() {
    apiRequest("GET", "/api/auth/status", null, function (status, data) {
      if (status === 200 && data && data.requires_initial_setup) {
        state.requiresSetup = true;
        el("auth-title").textContent = "Configuración Inicial de Administrador";
        el("auth-subtitle").textContent = "No hay usuarios registrados. Crea la cuenta principal.";
        el("field-fullname").classList.remove("hidden");
        el("auth-submit").textContent = "Crear Administrador";
        el("view-auth").classList.remove("hidden");
        return;
      }

      apiRequest("GET", "/api/auth/me", null, function (meStatus, user) {
        if (meStatus === 200 && user) {
          renderAuthenticatedView(user);
        } else {
          el("view-auth").classList.remove("hidden");
        }
      });
    });
  }

  el("auth-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var endpoint = state.requiresSetup ? "/api/auth/setup" : "/api/auth/login";
    var payload = {
      username: el("auth-username").value,
      password: el("auth-password").value
    };
    if (state.requiresSetup) {
      payload.full_name = el("auth-fullname").value;
    }
    apiRequest("POST", endpoint, payload, function (status, data) {
      if (status >= 200 && status < 300 && data && data.user) {
        el("auth-error").classList.add("hidden");
        renderAuthenticatedView(data.user);
      } else {
        el("auth-error").textContent = (data && data.detail) || "Error de autenticación.";
        el("auth-error").classList.remove("hidden");
      }
    });
  });

  el("btn-logout").addEventListener("click", function () {
    apiRequest("POST", "/api/auth/logout", {}, function () {
      window.location.reload();
    });
  });

  el("btn-enable-audio").addEventListener("click", function () {
    var player = el("pos-audio-player");
    player.play().catch(function () {});
    state.audioUnlocked = true;
    el("btn-enable-audio").textContent = "Audio Web Habilitado";
  });

  var tabBtns = document.querySelectorAll(".tab-btn");
  for (var i = 0; i < tabBtns.length; i++) {
    tabBtns[i].addEventListener("click", function (ev) {
      var target = ev.currentTarget.getAttribute("data-tab");
      var allBtns = document.querySelectorAll(".tab-btn");
      for (var j = 0; j < allBtns.length; j++) {
        allBtns[j].classList.remove("active");
      }
      ev.currentTarget.classList.add("active");
      var sections = document.querySelectorAll(".tab-section");
      for (var k = 0; k < sections.length; k++) {
        sections[k].classList.add("hidden");
      }
      el("tab-" + target).classList.remove("hidden");
    });
  }

  el("btn-rotate-token").addEventListener("click", function () {
    apiRequest("POST", "/api/admin/config/rotate-token", {}, function (status) {
      if (status === 200) {
        loadAdminPanel();
      }
    });
  });

  el("btn-test-sound").addEventListener("click", function () {
    apiRequest("POST", "/api/admin/test-sound?amount=50000", {}, function () {});
  });

  el("btn-search-history").addEventListener("click", function () {
    var s = el("filter-start").value;
    var e = el("filter-end").value;
    if (!s || !e) {
      return;
    }
    apiRequest("GET", "/api/deposits/history?start_date=" + s + "&end_date=" + e, null, function (status, rows) {
      var tbody = el("history-tbody");
      tbody.innerHTML = "";
      if (status !== 200 || !rows || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">Sin registros en el rango seleccionado.</td></tr>';
        return;
      }
      for (var i = 0; i < rows.length; i++) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" + rows[i].captured_at + "</td>" +
          "<td>" + rows[i].account_alias + "</td>" +
          "<td>" + rows[i].sender_name + "</td>" +
          "<td><code>" + rows[i].idempotency_hash.slice(0, 12) + "</code></td>" +
          '<td class="text-right">' + formatCOP(rows[i].amount_cop) + "</td>";
        tbody.appendChild(tr);
      }
    });
  });

  el("btn-export-csv").addEventListener("click", function () {
    var s = el("filter-start").value;
    var e = el("filter-end").value;
    if (!s || !e) {
      return;
    }
    window.location.href = "/api/deposits/export?start_date=" + s + "&end_date=" + e;
  });

  el("form-new-cashier").addEventListener("submit", function (e) {
    e.preventDefault();
    apiRequest("POST", "/api/admin/users", {
      username: el("cashier-user").value,
      full_name: el("cashier-name").value,
      password: el("cashier-pass").value
    }, function (status) {
      if (status === 201) {
        el("form-new-cashier").reset();
        loadAdminPanel();
      }
    });
  });

  el("form-new-account").addEventListener("submit", function (e) {
    e.preventDefault();
    apiRequest("POST", "/api/admin/accounts", {
      alias: el("acc-alias").value,
      phone_number: el("acc-phone").value,
      device_label: el("acc-device").value
    }, function (status) {
      if (status === 201) {
        el("form-new-account").reset();
        loadAdminPanel();
      }
    });
  });

  checkSessionOrSetup();
})();
