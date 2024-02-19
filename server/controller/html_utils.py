def to_html(obj, indent = 1):
    if isinstance(obj, list):
        htmls = []
        for k in obj:
            htmls.append(to_html(k,indent+1))
        return '[<div style="margin-left: %dem">%s</div>]' % (indent, ',<br>'.join(htmls))

    if isinstance(obj, dict):
        htmls = []
        for k,v in obj.items():
            htmls.append("<span style='font-style: italic; color: #888'>%s</span>: %s" % (k,to_html(v,indent+1)))
        return '{<div style="margin-left: %dem">%s</div>}' % (indent, ',<br>'.join(htmls))
    return str(obj)