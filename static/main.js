function toggleMode(){
    document.body.classList.toggle("dark")
    localStorage.setItem("theme", document.body.classList.contains("dark") ? "dark" : "light")
}

window.onload = function(){
    if(localStorage.getItem("theme") === "dark"){
        document.body.classList.add("dark")
    }
    loadRecent()
}

async function loginUser(){
    const username = document.getElementById("username").value
    const password = document.getElementById("password").value
    const response = await fetch("/login_user", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({username,password})
    })
    const data = await response.json()
    if(data.success){ window.location.href="/" } else { alert("Invalid credentials") }
}

async function signupUser(){
    const username = document.getElementById("username").value
    const password = document.getElementById("password").value
    const response = await fetch("/signup_user", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({username,password})
    })
    const data = await response.json()
    if(data.success){ document.getElementById("successMsg").innerText="Signup successful!" } else { alert("Username already exists") }
}

const diseaseInput = document.getElementById("disease")
const suggestionsList = document.getElementById("suggestions")
const form = document.getElementById("diseaseForm")

if(diseaseInput){
    diseaseInput.addEventListener("input", async ()=>{
        const query = diseaseInput.value
        if(query.length < 1){ suggestionsList.innerHTML=""; return }
        const response = await fetch("/get_diseases", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body: JSON.stringify({disease: query})
        })
        const data = await response.json()
        suggestionsList.innerHTML=""
        data.diseases.forEach(name=>{
            const li = document.createElement("li")
            li.textContent = name
            li.onclick = ()=>{ diseaseInput.value = name; suggestionsList.innerHTML="" }
            suggestionsList.appendChild(li)
        })
    })
}

if(form){
    form.addEventListener("submit", async (e)=>{
        e.preventDefault()
        const disease = document.getElementById("disease").value
        const age = document.getElementById("age").value
        const gender = document.getElementById("gender").value
        const response = await fetch("/get_medicines", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body: JSON.stringify({disease,age,gender})
        })
        const data = await response.json()
        await fetch("/save_search", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body: JSON.stringify({disease,age,gender})
        })
        localStorage.setItem("resultData", JSON.stringify(data))
        window.location.href="/results"
    })
}

if(document.getElementById("result")){
    const data = JSON.parse(localStorage.getItem("resultData"))
    const resultDiv = document.getElementById("result")
    if(!data || data.medicines.length === 0){
        resultDiv.innerHTML = "<p>No medicines found.</p>"
    } else {
        let html = `<h3>Disease Description</h3><p>${data.description}</p><h3>Medicines</h3>`
        data.medicines.forEach(med=>{
            html += `<div class="medicine-card">
            <div class="medicine-name">${med.name} (₹${med.cost})</div>
            <div class="dosage">Dosage: ${med.dosage}</div>
            <ul>${med.precautions.split(".").map(p=>p.trim()).filter(p=>p).map(p=>`<li>${p}</li>`).join("")}</ul>
            </div>`
        })
        resultDiv.innerHTML = html
    }
}

const bookmarkBtn = document.getElementById("bookmarkBtn")
if(bookmarkBtn){
    bookmarkBtn.style.marginTop = "20px"
    bookmarkBtn.style.padding = "10px 20px"
    bookmarkBtn.style.backgroundColor = "#1e90ff"
    bookmarkBtn.style.color = "white"
    bookmarkBtn.style.border = "none"
    bookmarkBtn.style.borderRadius = "6px"
    bookmarkBtn.style.cursor = "pointer"
    bookmarkBtn.onmouseover = ()=>{bookmarkBtn.style.backgroundColor = "#1c86ee"}
    bookmarkBtn.onmouseout = ()=>{bookmarkBtn.style.backgroundColor = "#1e90ff"}
    bookmarkBtn.onclick = async ()=>{
        const data = JSON.parse(localStorage.getItem("resultData"))
        const diseaseName = data.disease || "Unknown"
        await fetch("/bookmark", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body: JSON.stringify({disease: diseaseName, result: data})
        })
        alert("Saved")
    }
}

async function loadRecent(){
    const list = document.getElementById("recentList")
    if(!list) return
    const response = await fetch("/get_recent")
    const data = await response.json()
    list.innerHTML = ""
    data.searches.forEach(s=>{
        const li = document.createElement("li")
        li.textContent = s.disease + " (" + s.age + ", " + s.gender + ")"
        list.appendChild(li)
    })
}

const deleteBtn = document.getElementById("deleteAccountBtn")
if(deleteBtn){
    deleteBtn.addEventListener("click", async ()=>{
        if(!confirm("Are you sure you want to delete your account? This cannot be undone.")) return
        const response = await fetch("/delete_account", { method: "POST" })
        const data = await response.json()
        if(data.success){
            alert("Account deleted successfully.")
            window.location.href = "/"
        } else { alert("Failed to delete account.") }
    })
}
