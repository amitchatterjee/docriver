class Viewer extends HTMLElement {
    constructor() {
        super();   
    }

    viewDocument(viewer, params) {
        console.log(params);
        let docServer = viewer.getAttribute('docServer')? this.getAttribute('docServer'): "";
        let url = docServer + '/document/' + this.getAttribute("realm") + '/' + this.getAttribute("document") + '?authorization=' + params.authorization;
        let target = viewer.getAttribute('target')? this.getAttribute('target'): "_blank";
        open(url, target);
    }

    handleDocumentView(viewer) {
        viewer.shadowRoot.addEventListener('click', function(event) {
            event.preventDefault();

            let fn = window[viewer.getAttribute('onDocumentView')];
            if (fn) {
                fn(viewer, function(params) {
                    viewer.viewDocument(viewer, params);
                });
            } else {
                viewer.viewDocument(viewer, {});
            }
        });
    }
    
    connectedCallback() {
        console.log('Conected to docriver-viewer for realm: ' + this.getAttribute("realm"));

        const shadowRoot = this.attachShadow({ mode: "open" });
        const template = document.querySelector("#docViewerTemplate");
        if (template != null) {
            console.log("Since a template has been provided, going to use it");
            const clone = template.content.cloneNode(true);
            shadowRoot.append(clone);
        } else {
            console.log("Since a template has not been provided, going to use the default view")
            shadowRoot.innerHTML = `
            <div class="docriverViewerBox">
                <a>Click here to view the document</a>
            </div>
            `;
            this.addStyles();
        }

        this.handleDocumentView(this);
    }

    addStyles() {
        Array.from(document.styleSheets).forEach((styleSheet) => {
            // console.log(styleSheet);
            Array.from(styleSheet.cssRules).forEach((cssRule) => {
                if (cssRule.selectorText && cssRule.selectorText.startsWith('docriver-viewer-basic')) {
                    const rule = cssRule.cssText.replace('docriver-viewer-basic ', '');
                    const styleSheet = document.createElement('style');
                    this.shadowRoot.appendChild(styleSheet);
                    styleSheet.sheet.insertRule(rule);
                }
            });
        });
    }
}

if(!customElements.get('docriver-viewer-basic')) {
    customElements.define('docriver-viewer-basic', Viewer);
}
