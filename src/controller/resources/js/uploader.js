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

    connectedCallback() {
        console.log('Conected to docriver-uploader for realm: ' + this.getAttribute("realm"));
        this.attachShadow({ mode: "open" }).innerHTML = `
        <form method="POST" target="result" enctype="multipart/form-data">
        <label for="files">Files</label>
        <input type="file" id="files" name="files" required multiple>
        <input type="submit" value="Submit">
        </form>
        <iframe name="result">
        `;
        this.form = this.shadowRoot.querySelector("form");
        this.form.action = this.getAttribute('docServer') + "/tx/" + this.getAttribute("realm")

        this.form.addEventListener("submit", (e) => {
            this.form.hidden=true;
            this.resultFrame.hidden=false;
        });

        this.createHidden('refResourceType', this.getAttribute("refResourceType"));
        this.createHidden('refResourceId', this.getAttribute("refResourceId"));
        this.createHidden('refResourceDescription', this.getAttribute("refResourceDescription"));

        this.resultFrame = this.shadowRoot.querySelector("iframe");
        this.resultFrame.hidden=true;
    }
}

customElements.define('docriver-uploader', Uploader);