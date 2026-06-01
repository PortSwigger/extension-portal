package burp.model;

public class WASFinding implements Comparable<WASFinding>{

	String findingId;
	String findingName;
	public WASFinding(String findingId, String findingName) {
		super();
		this.findingId = findingId;
		this.findingName = findingName;
	}
	public String getFindingId() {
		return findingId;
	}
	public void setFindingId(String findingId) {
		this.findingId = findingId;
	}
	public String getFindingName() {
		return findingName;
	}
	public void setFindingName(String findingName) {
		this.findingName = findingName;
	}
	

	@Override
	public int compareTo(WASFinding o) {
		return this.findingName.compareToIgnoreCase(o.getFindingName());
	}
	
	 @Override
	  public String toString() {
	      return this.findingId + " - " + this.findingName ;
	  }
}
