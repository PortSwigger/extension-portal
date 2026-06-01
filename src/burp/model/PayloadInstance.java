package burp.model;

public class PayloadInstance implements Comparable<PayloadInstance> {

	private String qid;
	private String name;
	private String link;
	private String method;
	private String headers;
	private String body;
	private String payload;
	
	public PayloadInstance() {}
	
	public PayloadInstance(String qid, String name, String link, String method, String headers, String body, String payload) {
		super();
		this.qid = qid;
		this.name = name;
		this.link = link;
		this.method = method;
		this.headers = headers;
		this.body = body;
		this.payload = payload;
	}

	
	public String getQid() {
		return qid;
	}

	public void setQid(String qid) {
		this.qid = qid;
	}

	public String getName() {
		return name;
	}

	public void setName(String name) {
		this.name = name;
	}

	public String getLink() {
		return link;
	}

	public void setLink(String link) {
		this.link = link;
	}

	public String getMethod() {
		return method;
	}

	public void setMethod(String method) {
		this.method = method;
	}

	public String getHeaders() {
		return headers;
	}

	public void setHeaders(String headers) {
		this.headers = headers;
	}

	public String getBody() {
		return body;
	}

	public void setBody(String body) {
		this.body = body;
	}

	public String getPayload() {
		return payload;
	}

	public void setPayload(String payload) {
		this.payload = payload;
	}

	@Override
	public int compareTo(PayloadInstance o) {
		return this.link.compareToIgnoreCase(o.getLink());
	}
	
	 @Override
	  public String toString() {
	      return this.method + " " + this.link ;
	  }
}
