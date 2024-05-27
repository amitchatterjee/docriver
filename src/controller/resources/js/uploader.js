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

    valid(form, formData) {
        const fileElementsList = [];
            let fileElements = form.querySelectorAll('input[type="file"]', 'input[name^="file"]');
            if (fileElements.length == 0) {
                throw new Error('No file inputs found in the form');
            }
            fileElements.forEach(fileElement=> {fileElementsList.push(fileElement.name);});

            for (let pair of formData.entries()) {
                if (fileElementsList.includes(pair[0]) && pair[1].name) {
                    return true;
                }
            }
            
            alert("No files selected");
            return false;
    }

    event(uploader, type, obj) {
        let event = new CustomEvent(type, {
            bubbles: true,
            cancelable: true,
            detail: obj
        });
        return uploader.dispatchEvent(event);
    }

    uploadDocument(uploader, form, formData, resultFrame) {
        resultFrame.hidden=false;

        const controller = new AbortController();
        const signal = controller.signal;

        const fetchPromise = fetch(new URL(form.action), {
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
                    console.log("Document submission result:");
                    console.log(json);
                    if (!uploader.event(uploader, "result", json)) {
                        return;
                    }

                    let txDiv = document.createElement('div');
                    txDiv.innerHTML = `Transaction Reference: <b>${json.tx}</b> - ${json.documents.length} document(s) submitted:`;
                    resultFrame.appendChild(document.createElement('p'));
                    resultFrame.appendChild(txDiv);
                    for(let i = 0; i < json.documents.length; i++) {
                        let docDiv = document.createElement('div');
                        docDiv.innerHTML = `&nbsp;&nbsp;&nbsp;&nbsp;(${i+1}) <b>${json.documents[i].document}</b>`;
                        resultFrame.appendChild(docDiv);
                    }
                    form.reset();
                });
            } else {
                response.text().then(error=> {
                    if (!uploader.event(uploader, "error", 
                        {
                            error: `${error}`
                        })) {
                        return;
                    }
                    alert(`Document(s) rejected. Error: ${error}`);
                });
            }
        }).catch(error => {
            console.error(`Error submitting document(s): ${error}`);
            if (!uploader.event(uploader, "error", 
                {
                    error: `${error}`
                })) {
                return;
            }
            alert(`Error while submitting documents: ${error}`);
        }).finally(()=>{
            clearTimeout(timerId);
        });

        const timerId = setTimeout(() => {
            controller.abort(); // Abort the fetch request
            console.error('Document submission timed out');
            if (!uploader.event(uploader, "error", 
                {
                    error: "Document submission timed out"
                })) {
                return;
            }
            alert("Document submission timed out");
        }, 60000);
    }

    handleDocumentSubmission(uploader) {
        uploader.shadowRoot.querySelector("form").addEventListener('submit', function(event) {
            event.preventDefault();
            // console.log(uploader);

            const resultFrame = uploader.shadowRoot.querySelector(".docriverSubmissionResult");
            const form = event.currentTarget;
            const formData = new FormData(form);
            //console.log(form);

            if (!uploader.valid(form, formData)) {
                return;
            }

            let fn = window[uploader.getAttribute('onDocumentSubmit')];
            if (fn) {
                fn(formData, function(extraAttributes) {
                    Object.entries(extraAttributes).forEach((entry) => {
                        const [key, value] = entry;
                        // console.log(`${key}: ${value}`);
                        formData.set(key, value);
                    });
                    uploader.uploadDocument(uploader, form, formData, resultFrame);
                });
            } else {
                uploader.uploadDocument(uploader, form, formData, resultFrame);
            }
        });
    }
    
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
                <div class="docriverSubmissionResult">
                </div>
                <p></p>
                <form id="docriverSubmissionForm" method="POST" enctype="multipart/form-data">
                    <label for="files">Select one or more files to submit.Click the Submit button when done:</label>
                    <br/>
                    <input type="file" id="files" name="files" multiple>
                    <input type="submit" value="Upload Document">
                    &nbsp;&nbsp;<input type="reset" value="Reset Selection">
                </form>
            </div>
            `;
            this.addStyles();

            let label = this.getAttribute("label");
            if (label != null) {
                const labelElement = shadowRoot.querySelector("label[for='files']");
                label = label.replace(/{{refResourceId}}/g, this.getAttribute("refResourceId"));
                labelElement.innerHTML = label;
            }
        }
        const form = shadowRoot.querySelector("form");
        let docUrl = this.getAttribute('docServer')? this.getAttribute('docServer'): "";
        form.action = docUrl + "/tx/" + this.getAttribute("realm")
        let resultFrame = shadowRoot.querySelector(".docriverSubmissionResult")
        resultFrame.hidden=true;
        resultFrame.innerHTML='';     

        this.createHidden(form, 'authorization', this.getAttribute("authorization"));
        this.createHidden(form, 'tx', this.getAttribute("tx"));
        this.createHidden(form, 'documentType', this.getAttribute("documentType"));
        this.createHidden(form, 'refResourceType', this.getAttribute("refResourceType"));
        this.createHidden(form, 'refResourceId', this.getAttribute("refResourceId"));
        this.createHidden(form, 'refResourceDescription', this.getAttribute("refResourceDescription"));

        let onResult = this.getAttribute('onResult');
        if (onResult) {
            let fn = window[onResult];
            this.addEventListener("result", fn);
        }

        let onError = this.getAttribute('onError');
        if (onError) {
            let fn = window[onError];
            this.addEventListener("error", fn);
        }

        this.handleDocumentSubmission(this);
    }

    addStyles() {
        Array.from(document.styleSheets).forEach((styleSheet) => {
            // console.log(styleSheet);
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

if(!customElements.get('docriver-uploader-basic')) {
    customElements.define('docriver-uploader-basic', Uploader);
}

function resetUpload() {
    let shadowRoot = document.querySelector('docriver-uploader-basic').shadowRoot;
    let form = shadowRoot.querySelector("#docriverSubmissionForm");
    form.reset();
    let result = shadowRoot.querySelector(".docriverSubmissionResult");
    result.innerHTML = '';
}

function submitDocuments() {
    let shadowRoot = document.querySelector('docriver-uploader-basic').shadowRoot;
    let form = shadowRoot.querySelector("#docriverSubmissionForm");
    let submitEvent = new SubmitEvent("submit", { submitter: form });
    form.dispatchEvent(submitEvent);
}

function getSubmittedDocuments() {
    // TODO
}

function removeSubmissionBox() {
    let shadowRoot = document.querySelector('docriver-uploader-basic').shadowRoot;
    let submissionBox = shadowRoot.querySelector(".docriverSubmissionBox");
    submissionBox.remove();
}