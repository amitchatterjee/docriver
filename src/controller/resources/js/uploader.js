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

    handleSubmit(event) {
        event.preventDefault();

        //this.resultFrame.hidden=false;

        const form = event.currentTarget;
        form.hidden=true;

        const url = new URL(form.action);
        const formData = new FormData(form);
        const controller = new AbortController();
        const signal = controller.signal;

        const fetchOptions = {
            method: form.method,
            cache: "no-cache",
            headers: {
                "Accept": "application/json",
            },
            redirect: "follow",
            body: formData,
            signal
        };
      
        const fetchPromise = fetch(url, fetchOptions);
        fetchPromise.then(response => {
            if (response.status == 200) {
                response.json().then(json=> {
                    console.log(json)
                });
            } else {
                console.log("########## " + response.body);
            }
        }).catch(error => {
            // Handle any errors that occurred during the fetch
            console.error('Fetch error:', error);
        }).finally(()=>{
            clearTimeout(timeoutId); // Clear the timeout
        });

        const timeoutId = setTimeout(() => {
            controller.abort(); // Abort the fetch request
            console.log('Document submission timed out');
        }, 5000);
    }

    connectedCallback() {
        console.log('Conected to docriver-uploader for realm: ' + this.getAttribute("realm"));
        this.attachShadow({ mode: "open" }).innerHTML = `
        <form method="POST" enctype="multipart/form-data">
        <label for="files">Files</label>
        <input type="file" id="files" name="files" required multiple>
        <input type="submit" value="Submit">
        </form>
        <iframe name="result">
        `;
        this.form = this.shadowRoot.querySelector("form");
        this.form.action = this.getAttribute('docServer') + "/tx/" + this.getAttribute("realm")

        this.form.addEventListener('submit', this.handleSubmit);

        /*
        this.form.addEventListener("submit", (e) => {
            this.form.hidden=true;
            this.resultFrame.hidden=false;
        });
        */

        this.createHidden('refResourceType', this.getAttribute("refResourceType"));
        this.createHidden('refResourceId', this.getAttribute("refResourceId"));
        this.createHidden('refResourceDescription', this.getAttribute("refResourceDescription"));

        this.resultFrame = this.shadowRoot.querySelector("iframe");
        this.resultFrame.hidden=true;
    }
}

customElements.define('docriver-uploader', Uploader);