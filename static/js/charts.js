const analyticsRoot = document.querySelector("#analytics-root");

if (analyticsRoot) {
    const currency = analyticsRoot.dataset.currency;
    const money = (value) => `${currency}${(value / 100).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}`;
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: "bottom" },
            tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${money(context.raw)}` } },
        },
        scales: { y: { beginAtZero: true, ticks: { callback: money } } },
    };

    fetch(analyticsRoot.dataset.endpoint, { headers: { Accept: "application/json" } })
        .then((response) => {
            if (!response.ok) throw new Error(`Analytics request failed: ${response.status}`);
            return response.json();
        })
        .then((data) => {
            new Chart(document.querySelector("#income-expense-chart"), {
                type: "bar",
                data: {
                    labels: data.monthly.labels,
                    datasets: [
                        { label: "Income", data: data.monthly.income_cents, backgroundColor: "#16a34a" },
                        { label: "Expenses", data: data.monthly.expense_cents, backgroundColor: "#dc2626" },
                    ],
                },
                options: commonOptions,
            });

            new Chart(document.querySelector("#spending-trend-chart"), {
                type: "line",
                data: {
                    labels: data.monthly.labels,
                    datasets: [{
                        label: "Expenses",
                        data: data.monthly.expense_cents,
                        borderColor: "#2563eb",
                        backgroundColor: "rgba(37, 99, 235, 0.12)",
                        fill: true,
                        tension: 0.3,
                    }],
                },
                options: commonOptions,
            });

            if (data.categories.labels.length) {
                new Chart(document.querySelector("#category-chart"), {
                    type: "doughnut",
                    data: {
                        labels: data.categories.labels,
                        datasets: [{
                            label: "Expenses",
                            data: data.categories.expense_cents,
                            backgroundColor: ["#2563eb", "#dc2626", "#d97706", "#16a34a", "#7c3aed", "#0891b2", "#db2777", "#64748b"],
                        }],
                    },
                    options: { ...commonOptions, scales: {} },
                });
            } else {
                document.querySelector("#category-chart").classList.add("d-none");
                document.querySelector("#category-empty").classList.remove("d-none");
            }

            if (data.budgets.labels.length) {
                new Chart(document.querySelector("#budget-chart"), {
                    type: "bar",
                    data: {
                        labels: data.budgets.labels,
                        datasets: [
                            { label: "Limit", data: data.budgets.limit_cents, backgroundColor: "#93c5fd" },
                            { label: "Spent", data: data.budgets.spent_cents, backgroundColor: "#f59e0b" },
                        ],
                    },
                    options: { ...commonOptions, indexAxis: "y" },
                });
            } else {
                document.querySelector("#budget-chart").classList.add("d-none");
                document.querySelector("#budget-empty").classList.remove("d-none");
            }
        })
        .catch(() => document.querySelector("#analytics-error").classList.remove("d-none"));
}
