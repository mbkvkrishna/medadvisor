const diseaseInput = document.getElementById("disease")
const suggestionsList = document.getElementById("suggestions")
const form = document.getElementById("diseaseForm")
const resultDiv = document.getElementById("result")

diseaseInput.addEventListener("input", async () => {
    const query = diseaseInput.value
    if(query.length < 1){
        suggestionsList.innerHTML = ""
        return
    }
    const response = await fetch("/get_diseases", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({disease: query})
    })
    const data = await response.json()
    suggestionsList.innerHTML = ""
    if(data.diseases.length === 0){
        const li = document.createElement("li")
        li.textContent = "No disease found"
        li.classList.add("no-suggestion")
        suggestionsList.appendChild(li)
        return
    }
    data.diseases.forEach(name => {
        const li = document.createElement("li")
        li.textContent = name
        li.onclick = () => {
            diseaseInput.value = name
            suggestionsList.innerHTML = ""
        }
        suggestionsList.appendChild(li)
    })
})

form.addEventListener("submit", async (e)=>{
    e.preventDefault()
    const disease = document.getElementById("disease").value
    const age = document.getElementById("age").value
    const gender = document.getElementById("gender").value

    const response = await fetch("/get_medicines", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({disease, age, gender})
    })
    const data = await response.json()

    if(data.medicines.length === 0){
        resultDiv.innerHTML = `<p style="text-align:center; font-style:italic; color:#555;">No medicines found for "${disease}".</p>`
        return
    }

    let html = `<h3>Disease Description</h3><p>${data.description}</p><h3>Medicines</h3>`
    data.medicines.forEach(med=>{
        html += `<div class="medicine-card">
            <p class="medicine-name">${med.name} <span>(₹${med.cost})</span></p>
            <p class="dosage">Dosage: ${med.dosage}</p>
            <ul>${med.precautions.split(".").map(p => p.trim()).filter(p=>p).map(p=>`<li>${p}</li>`).join("")}</ul>
        </div>`
    })
    resultDiv.innerHTML = html
})
