// SupportFlow AI — interações client-side (toasts + clipboard).

// Copia o conteúdo de um <textarea> para a área de transferência do navegador.
function copyText(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    navigator.clipboard.writeText(el.value).then(
        () => showToast("Resposta copiada!", "success"),
        () => showToast("Não foi possível copiar", "error")
    );
}

// Exibe um toast temporário no canto inferior direito.
function showToast(message, level = "success") {
    const colors = {
        success: "bg-emerald-700",
        error: "bg-red-700",
        info: "bg-blue-700",
    };
    const toast = document.createElement("div");
    toast.className =
        `${colors[level] || colors.info} text-white text-sm px-4 py-3 rounded-lg shadow-lg ` +
        "transition-all duration-300 opacity-0 translate-y-2";
    toast.textContent = message;
    document.getElementById("toast-container").appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.remove("opacity-0", "translate-y-2");
    });
    setTimeout(() => {
        toast.classList.add("opacity-0", "translate-y-2");
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Toasts disparados pelo servidor via header HX-Trigger: {"toast": {...}}.
document.body.addEventListener("toast", (evt) => {
    const detail = evt.detail || {};
    if (detail.message) showToast(detail.message, detail.level || "info");
});
