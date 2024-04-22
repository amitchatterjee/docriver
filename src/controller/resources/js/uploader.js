class Uploader extends HTMLElement {
    form = null;
    resultFrame = null;

    constructor() {
        super();   
    }

    createHidden(name, value) {
       if (value != null) {
        var field = document.createElement("input");
        field.setAttribute('type', 'hidden');
        field.setAttribute("value", value);
        field.setAttribute("name", name);
        this.form.appendChild(field);
       }
    }

    handleDocumentSubmission(resultFrame) {
        this.form.addEventListener('submit', function(event) {
            event.preventDefault();
    
            var form = event.currentTarget;
            form.hidden=true;
            resultFrame.hidden=false;
    
            var url = new URL(form.action);
            var formData = new FormData(form);
            const controller = new AbortController();
            var signal = controller.signal;
          
            const fetchPromise = fetch(url, {
                method: form.method,
                cache: "no-cache",
                headers: {
                    "Accept": "application/json",
                },
                redirect: "follow",
                body: formData,
                signal
            });
            fetchPromise.then(response => {
                if (response.status == 200) {
                    response.json().then(json=> {
                        console.log(json);
                        resultFrame.innerHTML = `${json.documents.length} document(s) submitted. Transaction Reference: <b>${json.tx}</b>`;
                    });
                } else {
                    response.text().then(error=> {
                        resultFrame.innerHTML = `Document(s) rejected. Error: <b>${error}</b>`;
                    });
                }
            }).catch(error => {
                console.error(`Error submitting document(s): ${error}`);
                resultFrame.innerHTML = `Error while submitting documents: <b>${error}</b>`;
            }).finally(()=>{
                clearTimeout(timerId);
            });
    
            const timerId = setTimeout(() => {
                controller.abort(); // Abort the fetch request
                resultFrame.innerHTML = "Document submission timed out";
            }, 60000);
        });
    }

    // formResetCallback() {}

    connectedCallback() {
        console.log('Conected to docriver-uploader for realm: ' + this.getAttribute("realm"));
        this.attachShadow({ mode: "open" }).innerHTML = `
        <form method="POST" enctype="multipart/form-data">
        <label for="files">Files</label>
        <input type="file" id="files" name="files" required multiple>
        <input type="submit" value="Submit">
        </form>
        <div>
            ....
        </div>
        `;
        this.form = this.shadowRoot.querySelector("form");
        this.form.action = this.getAttribute('docServer') + "/tx/" + this.getAttribute("realm")

        this.resultFrame = this.shadowRoot.querySelector("div");
        this.handleDocumentSubmission(this.resultFrame);

        this.createHidden('refResourceType', this.getAttribute("refResourceType"));
        this.createHidden('refResourceId', this.getAttribute("refResourceId"));
        this.createHidden('refResourceDescription', this.getAttribute("refResourceDescription"));

        this.resultFrame.hidden=true;
    }
}

customElements.define('docriver-uploader', Uploader);