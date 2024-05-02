class Uploader extends HTMLElement {
    constructor() {
        super();   
    }

    createHidden(form, name, value) {
       if (value != null) {
        var field = document.createElement("input");
        field.setAttribute('type', 'hidden');
        field.setAttribute("value", value);
        field.setAttribute("name", name);
        form.appendChild(field);
       }
    }

    handleDocumentSubmission(uploader) {
        uploader.shadowRoot.querySelector("form").addEventListener('submit', function(event) {
            event.preventDefault();
            console.log(uploader);
    
            var resultFrame = uploader.shadowRoot.querySelector(".docriverSubmissionResult");
            var form = event.currentTarget;

            form.hidden=true;
            resultFrame.hidden=false;
    
            var controller = new AbortController();
            var signal = controller.signal;
          
            const fetchPromise = fetch(new URL(form.action), {
                method: form.method,
                cache: "no-cache",
                headers: {
                    "Accept": "application/json",
                },
                redirect: "follow",
                body: new FormData(form),
                signal
            });
            fetchPromise.then(response => {
                if (response.status == 200) {
                    response.json().then(json=> {
                        console.log(json);
                        resultFrame.innerHTML = `${json.documents.length} document(s) submitted. Transaction Reference: <b>${json.tx}</b>`;
                        for(let i = 0; i < json.documents.length; i++) {
                            let newDiv = document.createElement('div');
                            newDiv.innerHTML = `&nbsp;&nbsp;&nbsp;&nbsp;Document ${i+1}: <b>${json.documents[i].document}</b>`;
                            resultFrame.appendChild(newDiv);
                        }
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

        const shadowRoot = this.attachShadow({ mode: "open" });
        const template = document.querySelector("#docSubmissionTemplate");
        if (template != null) {
            console.log("Since a template has been provided, going to use it");
            const clone = template.content.cloneNode(true);
            shadowRoot.append(clone);
        } else {
            console.log("Since a template has not been provided, going to use the default view")
            shadowRoot.innerHTML = `
            <div class="docriverSubmissionBox">
                <form id="docriverSubmissionForm" method="POST" enctype="multipart/form-data">
                <label for="files">Select one or more files.Click the Submit button when done:</label>
                <br/>
                <input type="file" id="files" name="files" required multiple>
                <input type="submit" value="Submit">
                </form>

                <div class="docriverSubmissionResult">
                ....
                </div>
            </div>
            `;
            this.addStyles();
        }
        const form = shadowRoot.querySelector("form");
        form.action = this.getAttribute('docServer') + "/tx/" + this.getAttribute("realm")
        shadowRoot.querySelector(".docriverSubmissionResult").hidden=true;
        this.createHidden(form, 'authorization', this.getAttribute("authorization"));
        this.createHidden(form, 'tx', this.getAttribute("tx"));
        this.createHidden(form, 'documentType', this.getAttribute("documentType"));
        this.createHidden(form, 'refResourceType', this.getAttribute("refResourceType"));
        this.createHidden(form, 'refResourceId', this.getAttribute("refResourceId"));
        this.createHidden(form, 'refResourceDescription', this.getAttribute("refResourceDescription"));

        this.handleDocumentSubmission(this);
    }

    addStyles() {
        Array.from(document.styleSheets).forEach((styleSheet) => {
            console.log(styleSheet);
            Array.from(styleSheet.cssRules).forEach((cssRule) => {
                if (cssRule.selectorText && cssRule.selectorText.startsWith('docriver-uploader-basic')) {
                    const rule = cssRule.cssText.replace('docriver-uploader-basic ', '');
                    const styleSheet = document.createElement('style');
                    this.shadowRoot.appendChild(styleSheet);
                    styleSheet.sheet.insertRule(rule);
                }
            });
        });
    }
}

customElements.define('docriver-uploader-basic', Uploader);