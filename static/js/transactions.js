const typeSelect = document.querySelector("#type");
const categorySelect = document.querySelector("#category_id");

function showMatchingCategories() {
    const selectedType = typeSelect.value;
    let selectedStillValid = false;

    for (const option of categorySelect.options) {
        if (!option.value) continue;
        const matches = option.dataset.type === selectedType;
        option.hidden = !matches;
        option.disabled = !matches;
        if (matches && option.selected) selectedStillValid = true;
    }

    if (!selectedStillValid) categorySelect.value = "";
}

if (typeSelect && categorySelect) {
    typeSelect.addEventListener("change", showMatchingCategories);
    showMatchingCategories();
}
