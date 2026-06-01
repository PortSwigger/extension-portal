package burp.model;

public class WebAppItem implements Comparable<WebAppItem>{
  private String id;
  private String name;
  private String url;
  private static int MAX_Length_Truncted_Name = 50;
  private static int MAX_Length_Truncted_URL = 80;
  
  public WebAppItem(String id, String name, String url) { this.id = id;
    this.name = name;
    this.url = url;
  }
  
  public void setWebAppItem_ID(String id) {
    this.id = id;
  }
  
  public void setWebAppItem_Name(String name) {
    this.name = name;
  }
  
  public void setWebAppItem_URL(String url) { this.url = url; }
  
  public String getWebAppItem_ID()
  {
    return id;
  }
  
  public String getWebAppItem_Name() {
    return name;
  }
  
  public String getWebAppItem_URL() { return url; }
  
  public String trunct_padding(String originalString, int maxm_size_padding)
  {
    String truncted_padding_string = originalString;
    if (originalString.length() >= maxm_size_padding) {
      truncted_padding_string = originalString.substring(0, maxm_size_padding - 1);
    }
    String padding_string = String.format("%1$-" + maxm_size_padding + "s", new Object[] { truncted_padding_string });
    return padding_string;
  }
  
  public String getWebAppItemName_TrunctedAndPadded()
  {
    return trunct_padding(name, MAX_Length_Truncted_Name);
  }
  
  public String getWebAppItemURL_TrunctedAndPadded()
  {
    return trunct_padding(url, MAX_Length_Truncted_URL);
  }
  
  public String getName() {
      return name;
  }

  public void setName(String name) {
      this.name = name;
  }

  @Override
  public int compareTo(WebAppItem o) {
      return this.name.compareToIgnoreCase(o.getName()); // WebApp name sort in ascending order  
  }

  @Override
  public String toString() {
      return this.name;
  }
}
