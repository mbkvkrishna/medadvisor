function toggleMode(){
    document.body.classList.toggle("dark")
    localStorage.setItem("theme",document.body.classList.contains("dark")?"dark":"light")
}
window.onload=function(){
    if(localStorage.getItem("theme")==="dark"){
        document.body.classList.add("dark")
    }
}

const diseaseInput=document.getElementById("disease")
const suggestionsList=document.getElementById("suggestions")
const form=document.getElementById("diseaseForm")

if(diseaseInput){
diseaseInput.addEventListener("input",async()=>{
    const query=diseaseInput.value
    if(query.length<1){
        suggestionsList.innerHTML=""
        return
    }
    const response=await fetch("/get_diseases",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({disease:query})})
    const data=await response.json()
    suggestionsList.innerHTML=""
    data.diseases.forEach(name=>{
        const li=document.createElement("li")
        li.textContent=name
        li.onclick=()=>{diseaseInput.value=name;suggestionsList.innerHTML=""}
        suggestionsList.appendChild(li)
    })
})
}

if(form){
form.addEventListener("submit",async(e)=>{
    e.preventDefault()
    const disease=document.getElementById("disease").value
    const age=document.getElementById("age").value
    const gender=document.getElementById("gender").value
    const response=await fetch("/get_medicines",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({disease,age,gender})})
    const data=await response.json()
    localStorage.setItem("resultData",JSON.stringify(data))
    window.location.href="/results"
})
}

if(document.getElementById("result")){
    const data=JSON.parse(localStorage.getItem("resultData"))
    const resultDiv=document.getElementById("result")
    if(!data||data.medicines.length===0){
        resultDiv.innerHTML="<p>No medicines found.</p>"
    }else{
        let html=`<h3>Disease Description</h3><p>${data.description}</p><h3>Medicines</h3>`
        data.medicines.forEach(med=>{
            html+=`<div class="medicine-card">
            <div class="medicine-name">${med.name} (₹${med.cost})</div>
            <div class="dosage">Dosage: ${med.dosage}</div>
            <ul>${med.precautions.split(".").map(p=>p.trim()).filter(p=>p).map(p=>`<li>${p}</li>`).join("")}</ul>
            </div>`
        })
        resultDiv.innerHTML=html
    }
}
