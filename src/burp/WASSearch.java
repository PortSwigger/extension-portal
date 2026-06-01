package burp;

import java.io.PrintWriter;
import java.io.StringReader;
import java.io.StringWriter;
import java.net.MalformedURLException;
import java.net.URL;
import java.security.KeyManagementException;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.InputSource;

import burp.exception.PayloadInstanceException;
import burp.exception.UnauthorizedException;
import burp.model.PayloadInstance;
import burp.model.WASFinding;
import burp.model.WebAppItem;

public class WASSearch
{
	private String portal_username = "";
	private String portal_password = "";
	private static final String AUTHENTICATION_FAILED_CODE = "INVALID_CREDENTIALS";
	private static final String UNAUTHORIZED_CODE = "UNAUTHORIZED";
	private  int httpResponseCodeForWebapps ;
	private SimpleDateFormat time_formatter = new SimpleDateFormat("yyyy-MM-dd_HH:mm:ss.SSS");
	private IBurpExtenderCallbacks callbacks;
	private String api_url;
	private static String searchWebappApiPath = "/qps/rest/3.0/search/was/webapp";
	private static String searchFindingsApiPath = "/qps/rest/3.0/search/was/finding";
	private static String getFindingDetailsApiPath = "/qps/rest/3.0/get/was/finding/";


	public WASSearch(String post_url, String username_login, String password_login, IBurpExtenderCallbacks callbacks) {
		this.api_url = post_url;
		portal_username = username_login;
		portal_password = password_login;
		this.callbacks = callbacks;
	}

	private void disableSSLCertificateChecking()
	{
		TrustManager[] trustAllCerts = { new X509TrustManager() {
			public X509Certificate[] getAcceptedIssuers() { return null; }

			public void checkClientTrusted(X509Certificate[] arg0, String arg1)
					throws CertificateException
			{
				arg0[0].checkValidity();
			}



			public void checkServerTrusted(X509Certificate[] arg0, String arg1)
					throws CertificateException
			{
				arg0[0].checkValidity();
			}
		} };

		try
		{
			SSLContext sc = SSLContext.getInstance("TLS");

			sc.init(null, trustAllCerts, new SecureRandom());

			HttpsURLConnection.setDefaultSSLSocketFactory(sc.getSocketFactory());
		} catch (KeyManagementException | NoSuchAlgorithmException e) {
			StringWriter sw = new StringWriter();
			e.printStackTrace(new PrintWriter(sw));
			String stackTrace = sw.toString();
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Exception while processing SSL certificate checking; " + e.getMessage()+ "\n" + stackTrace + "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
		}
	}


	public String searchFindings(String webappId) {
		String responseData = "";
		disableSSLCertificateChecking();
		int httpResponseCode = -1;
		try {

			IExtensionHelpers helpers = callbacks.getHelpers();
			String uri = api_url + searchFindingsApiPath;
			URL url = new URL(uri);

			ArrayList<String> headers = new ArrayList<String>();
			headers.add("user: " + portal_username);
			headers.add("password: "+portal_password);
			headers.add("Content-Type: application/xml");
			headers.add("Host: "+ url.getHost());
			String postXmlData = String.format("<ServiceRequest>\n" +
					"<filters>\n" +
					" <Criteria field=\"webApp.id\" operator=\"EQUALS\">%s</Criteria>\n" +
					" <Criteria field=\"type\" operator=\"EQUALS\">VULNERABILITY</Criteria>\n" +
					" <Criteria field=\"status\" operator=\"IN\">NEW,ACTIVE,REOPENED</Criteria>\n" +
					" <Criteria field=\"findingType\" operator=\"EQUALS\">QUALYS</Criteria>\n" +
					"</filters>\n" +
					"</ServiceRequest>", webappId);

			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Making HTTP Request to : " + url + "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());

			String buildRequest = buildRequest(uri, "POST", headers, postXmlData);

			String protocol = url.getProtocol();
			Boolean isSSL = (protocol.equals("https"));

			byte[] response = callbacks.makeHttpRequest(url.getHost(), url.getPort() == -1 ? 443 : url.getPort(), isSSL, buildRequest.getBytes());

			IResponseInfo responseInfo = helpers.analyzeResponse(response);

			httpResponseCode = responseInfo.getStatusCode();
			int offset = responseInfo.getBodyOffset();
			byte[] responseBody = Arrays.copyOfRange(response, offset, response.length);
			responseData = new String(responseBody);
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + "Response code = " + httpResponseCode + "; Response data for search findings: \n" +responseData+"\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
			return responseData;
		}
		catch (Exception e) {
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Response Code = "+ httpResponseCode+ "\n Exception while fetching WAS findings for given webapp: " + e.getMessage()+ "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
		}
		return responseData;
	}

	public boolean hasMoreRecords(String response) {
		if (response == null) {
			return false;
		}
		DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
		try
		{
			factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
			DocumentBuilder builder = factory.newDocumentBuilder();
			Document doc = builder.parse(new InputSource(new StringReader(response)));
			Node hasMoreRecordsNode =  (doc.getElementsByTagName("hasMoreRecords") != null) ? doc.getElementsByTagName("hasMoreRecords").item(0) : null;
			boolean hasMoreRecords = hasMoreRecordsNode != null ? Boolean.parseBoolean(hasMoreRecordsNode.getFirstChild().getNodeValue()) : false;
			return hasMoreRecords;
		} catch (Exception e) {
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error parsing hasMoreRecords field in search findings response; exception = " + e.getMessage()+ "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
		}
		return false;
	}


	public ArrayList<WASFinding> parseFindings(String response) {
		ArrayList<WASFinding> findingsList = new ArrayList<WASFinding>();
		if (response == null) {
			return findingsList;
		}
		DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
		try
		{
			factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
			DocumentBuilder builder = factory.newDocumentBuilder();
			Document doc = builder.parse(new InputSource(new StringReader(response)));
			NodeList listofFindings = doc.getElementsByTagName("Finding");
			NodeList responseCodeNodeList = doc.getElementsByTagName("responseCode");
			if (listofFindings != null && listofFindings.getLength() > 0)
			{
				int nodeCount = listofFindings.getLength();
				for (int i = 0; i < nodeCount; i++) {
					Node findingNode = listofFindings.item(i);
					if (findingNode.getNodeType() == 1) {
						Element findingElement = (Element)findingNode;
						Node idNode =  (findingElement.getElementsByTagName("id") != null) ? findingElement.getElementsByTagName("id").item(0) : null;
						String id = idNode != null ? idNode.getFirstChild().getNodeValue() : "";

						Node nameNode = (findingElement.getElementsByTagName("name") != null) ? findingElement.getElementsByTagName("name").item(0) : null ;
						String name = nameNode != null ? nameNode.getFirstChild().getNodeValue() : "";


						if (!id.isEmpty() || !name.isEmpty()) {
							WASFinding wasFinding = new WASFinding(id, name);
							findingsList.add(wasFinding);
						}
					}
				}
			}
			else
			{
				Node responseCodeNode = responseCodeNodeList.item(0);
				if (responseCodeNode.getNodeType() == 1) {
					if (responseCodeNode.getFirstChild().getNodeValue().equalsIgnoreCase("SUCCESS")){
						BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " No Findings found in this response.\n");
						BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
					} else {
						BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error msg = " + responseCodeNode.getFirstChild().getNodeValue()+ "\n");
						BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
					}
				}
			}
		}
		catch (Exception e) {
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error fetching and parsing the WAS Findings; exception = " + e.getMessage()+ "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
		}
		Collections.sort(findingsList);
		return findingsList;
	}

	public String getWebApplicationList()
	{

		String responseData = "";
		disableSSLCertificateChecking();

		try {

			IExtensionHelpers helpers = callbacks.getHelpers();
			String uri = api_url+searchWebappApiPath;
			URL url = new URL(uri);

			ArrayList<String> headers = new ArrayList<String>();
			headers.add("user: " + portal_username);
			headers.add("password: "+portal_password);
			headers.add("Content-Type: application/json");
			headers.add("Host: "+ url.getHost());
			String postJsonData = "{  \n" +
					"   \"ServiceRequest\":{  \n" +
					"      \"preferences\":{  \n" +
					"         \"limitResults\":1000\n" +
					"      } \n" +
					"}\n" +
					"}  ";

			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Making HTTP Request to : " + url + "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());

			String buildRequest = buildRequest(uri, "POST", headers, postJsonData);

			String protocol = url.getProtocol();
			Boolean isSSL = (protocol.equals("https"));

			byte[] response = callbacks.makeHttpRequest(url.getHost(), url.getPort() == -1 ? 443 : url.getPort(), isSSL, buildRequest.getBytes());

			IResponseInfo responseInfo = helpers.analyzeResponse(response);

			httpResponseCodeForWebapps = responseInfo.getStatusCode();
			int offset = responseInfo.getBodyOffset();
			byte[] responseBody = Arrays.copyOfRange(response, offset, response.length);
			responseData = new String(responseBody);
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Response data for Get Webapps list: \n" +responseData+"\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
			return responseData;
		}
		catch (Exception e) {
			httpResponseCodeForWebapps = -1; // it means an error is encountered
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Exception while fetching webapps; Please check credentials: " + e.getMessage()+ "\n" + "###### Response Data ##### \n" +responseData+"\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
		}
		return responseData;
	}


	private String buildRequest(String URL, String method, ArrayList<String> headers, String body) {
		IExtensionHelpers helpers = callbacks.getHelpers();
		String buildRequest = "";
		try {
			URL url = new URL(URL);

			byte[] httpHeadersAndBody = helpers.buildHttpMessage(headers, body != null ? body.getBytes() : null);
			byte[] requestProps = helpers.stringToBytes(method + " " + url.getPath()+" HTTP/1.1\r\n");

			buildRequest = new String(requestProps) + new String(httpHeadersAndBody);

			String maskedPasswordRequest = buildRequest;
			maskedPasswordRequest = maskedPasswordRequest.replaceAll("password: ([\\s\\S]*?)\\n", "password: XXXXXX\n");

			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Request data : " + maskedPasswordRequest +"\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());

		} catch (MalformedURLException e) {
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Malformed URL exception : " + e.getMessage());
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
		}

		return buildRequest;
	}

	public String getResponseCode(String response)
	{
		DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();

		try {
			factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
		} catch (ParserConfigurationException ex) {
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Exception ; " + ex.getMessage()+ "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
			return "";
		}

		String response_message_code = "";
		try {
			DocumentBuilder builder = factory.newDocumentBuilder();
			Document doc = builder.parse(new InputSource(new StringReader(response)));
			NodeList listofErrorResponse = doc.getElementsByTagName("responseCode");
			Node responseMessage = listofErrorResponse.item(0);
			if (responseMessage.getNodeType() == 1) {
				response_message_code = responseMessage.getFirstChild().getNodeValue();
			}
		}
		catch (Exception e)
		{
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Exception ; " + e.getMessage()+ "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
			return AUTHENTICATION_FAILED_CODE;
		}

		return response_message_code;
	}

	public boolean checkAuthenticationStatus(String response)
	{
		if( httpResponseCodeForWebapps!=200){
			return false;
		}
		else{
			String authentication_response = getResponseCode(response);
			if (authentication_response.equals(AUTHENTICATION_FAILED_CODE) || authentication_response.equals(UNAUTHORIZED_CODE)) {
				BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error msg = " + authentication_response+ "\n");
				BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
				return false;
			}
			return true;
		}
	}

	public ArrayList<WebAppItem> parseWebApplications(String response)
	{
		ArrayList<WebAppItem> webapplists = new ArrayList<WebAppItem>();

		DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
		try
		{
			factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
			DocumentBuilder builder = factory.newDocumentBuilder();
			Document doc = builder.parse(new InputSource(new StringReader(response)));
			NodeList listofWebApplications = doc.getElementsByTagName("WebApp");
			NodeList listofErrorResposne = doc.getElementsByTagName("responseCode");
			if (listofWebApplications != null && listofWebApplications.getLength() > 0)
			{
				int nodeCount = listofWebApplications.getLength();
				BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Total number of Web apps = " + nodeCount + "\n");
				BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
				for (int i = 0; i < nodeCount; i++) {
					Node webappNode = listofWebApplications.item(i);
					if (webappNode.getNodeType() == 1) {
						Element webAppElement = (Element)webappNode;
						Node webapp_ID_Node = webAppElement.getElementsByTagName("id").item(0);
						String webApp_id = webapp_ID_Node.getFirstChild().getNodeValue();

						Node webapp_Name_Node = webAppElement.getElementsByTagName("name").item(0);
						String webApp_name = webapp_Name_Node.getFirstChild().getNodeValue();

						Node webapp_URL_Node = webAppElement.getElementsByTagName("url").item(0);
						String webApp_URL = webapp_URL_Node.getFirstChild().getNodeValue();

						WebAppItem webAppItem = new WebAppItem(webApp_id, webApp_name, webApp_URL);
						webapplists.add(webAppItem);
					}
				}
			}
			else
			{
				Node authErrorMessage = listofErrorResposne.item(0);
				if (authErrorMessage.getNodeType() == 1) {
					BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error msg = " + authErrorMessage.getFirstChild().getNodeValue()+ "\n");
					BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
				}
			}
		}
		catch (Exception e) {
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error fetching and parsing the web apps list for given platform; exception = " + e.getMessage()+ "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
		}
		Collections.sort(webapplists);
		return webapplists;
	}

	public String getFindingDetails(String findingId) {
		String responseData = "";
		disableSSLCertificateChecking();
		int httpResponseCode = -1;
		try {

			IExtensionHelpers helpers = callbacks.getHelpers();
			String uri = api_url + getFindingDetailsApiPath + findingId;
			URL url = new URL(uri);

			ArrayList<String> headers = new ArrayList<String>();
			headers.add("user: " + portal_username);
			headers.add("password: "+portal_password);
			headers.add("Host: "+ url.getHost());

			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Making HTTP Request to : " + uri + "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());

			String buildRequest = buildRequest(uri, "GET", headers, null);

			String protocol = url.getProtocol();
			Boolean isSSL = (protocol.equals("https"));

			byte[] response = callbacks.makeHttpRequest(url.getHost(), url.getPort() == -1 ? 443 : url.getPort(), isSSL, buildRequest.getBytes());

			IResponseInfo responseInfo = helpers.analyzeResponse(response);

			httpResponseCode = responseInfo.getStatusCode();
			int offset = responseInfo.getBodyOffset();
			byte[] responseBody = Arrays.copyOfRange(response, offset, response.length);
			responseData = new String(responseBody);
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Response code = " + httpResponseCode + "; Response data for Get Finding details for finding ID " + findingId + " :\n" +responseData+"\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
			return responseData;
		}
		catch (Exception e) {
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " :  Response Code = " + httpResponseCode +"\nException while Finding details for finding ID " + findingId + " : " + e.getMessage()+ "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
		}
		return responseData;
	}

	public ArrayList<PayloadInstance> parsePayloadInstance(String response) throws PayloadInstanceException, UnauthorizedException
	{
		ArrayList<PayloadInstance> payloadList = new ArrayList<PayloadInstance>();
		if (response == null) {
			return payloadList;
		}

		DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
		try
		{
			factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
			DocumentBuilder builder = factory.newDocumentBuilder();
			Document doc = builder.parse(new InputSource(new StringReader(response)));
			NodeList listofPayloadInstances = doc.getElementsByTagName("PayloadInstance");
			NodeList responseCodeNodeList = doc.getElementsByTagName("responseCode");
			NodeList findingTypeNodeList = doc.getElementsByTagName("findingType");

			Node qidNode =  (doc.getElementsByTagName("qid") != null) ? doc.getElementsByTagName("qid").item(0) : null;
			String qid = qidNode != null ? qidNode.getFirstChild().getNodeValue() : "";
			Node nameNode =  (doc.getElementsByTagName("name") != null) ? doc.getElementsByTagName("name").item(0) : null;
			String name = nameNode != null ? nameNode.getFirstChild().getNodeValue() : "";

			if (findingTypeNodeList != null && findingTypeNodeList.getLength() > 0) {
				Node findingTypeNode = findingTypeNodeList.item(0);
				if (!findingTypeNode.getFirstChild().getNodeValue().equalsIgnoreCase("QUALYS")) {
					throw new PayloadInstanceException("Only finding type of QUALYS is supported");
				}
			}

			if (!(listofPayloadInstances == null || listofPayloadInstances.getLength() == 0))
			{
				int nodeCount = listofPayloadInstances.getLength();
				for (int i = 0; i < nodeCount; i++) {
					Node payloadInstanceNode = listofPayloadInstances.item(i);
					if (payloadInstanceNode.getNodeType() == 1) {
						Element payloadElement = (Element)payloadInstanceNode;
						Node methodNode =  (payloadElement.getElementsByTagName("method") != null) ? payloadElement.getElementsByTagName("method").item(0) : null;
						String method = methodNode != null ? methodNode.getFirstChild().getNodeValue() : "";

						Node linkNode = (payloadElement.getElementsByTagName("link") != null) ? payloadElement.getElementsByTagName("link").item(0) : null ;
						String link = linkNode != null ? linkNode.getFirstChild().getNodeValue() : "";

						Node headerNode = (payloadElement.getElementsByTagName("headers") != null) ? payloadElement.getElementsByTagName("headers").item(0) : null;
						String header = headerNode != null ? headerNode.getFirstChild().getNodeValue() : "";

						Node bodyNode = (payloadElement.getElementsByTagName("body") != null) ? payloadElement.getElementsByTagName("body").item(0) : null;
						String body = bodyNode != null ? bodyNode.getFirstChild().getNodeValue() : "";

						Node payloadNode = (payloadElement.getElementsByTagName("payload") != null) ? payloadElement.getElementsByTagName("payload").item(0) : null;
						String payload = payloadNode != null ? payloadNode.getFirstChild().getNodeValue() : "";

						if (!method.isEmpty() || !link.isEmpty() || !header.isEmpty() || !body.isEmpty() ) {
							PayloadInstance payloadInstance = new PayloadInstance(qid, name, link, method, header, body, payload);
							payloadList.add(payloadInstance);
						}
					}
				}


			}
			else
			{
				Node responseCodeNode = responseCodeNodeList.item(0);
				if (responseCodeNode.getNodeType() == 1) {
					String responseCode = responseCodeNode.getFirstChild().getNodeValue();
					if (responseCode.equalsIgnoreCase("SUCCESS")){
						BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " No Payloads found in this response.\n");
						BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
					} else if (responseCode.equalsIgnoreCase(UNAUTHORIZED_CODE)) {
						BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error msg = " + responseCodeNode.getFirstChild().getNodeValue()+ ". "
								+ "Please check if Qualys credentials and Finding ID is correct. \n");
						BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
						throw new UnauthorizedException("Unauthorized operation. Please check logs.");
					} else {
						BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error msg = " + responseCodeNode.getFirstChild().getNodeValue()+ "\n");
						BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
					}
				}
			}
		} catch(PayloadInstanceException e) {
			throw e;
		} catch (UnauthorizedException e) {
			throw e;
		} catch (Exception e) {
			StringWriter sw = new StringWriter();
			e.printStackTrace(new PrintWriter(sw));
			String exceptionAsString = sw.toString();
			BurpExtender.logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error fetching and parsing the payload instances list for given finding ID; exception = " + exceptionAsString + "\n");
			BurpExtender.logTextArea.setText(BurpExtender.logBuilder.toString());
		}
		return payloadList;
	}

}
