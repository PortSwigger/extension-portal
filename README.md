
Qualys WAS Burp Extension
==========================

The Qualys WAS Burp extension provides two useful features for Qualys Web Application Scanning (WAS) customers. 

First is the ability to import a WAS finding into Burp Repeater for manual validation of a WAS-discovered vulnerability. This feature works with both Burp Professional and Burp Community editions. Note that if a transient token is part of the imported request, such as a cookie for an authenticated session, you will need to update it manually.

Second is an option to send Burp scanner issues to Qualys WAS. This allows you to view and report Burp issues together with WAS findings for a more complete picture of your web application's security posture. Burp Suite Professional is required to use this feature.

To learn more about Qualys WAS, its integration with Burp, and the additional security and compliance solutions available on the Qualys Cloud Platform, please visit https://qualys.com/was-burp.

#### Requirements:
- Qualys WAS subscription, including API
- Burp Suite Professional or Burp Suite Community edition as noted above

#### Features:
- Import a Qualys WAS finding into Burp Repeater via context menu to manually validate it
- Send selected Burp scanner issues to Qualys WAS via context menu on Target tab
- Upstream proxy server settings in Burp are honored automatically
- All Qualys shared platforms and private cloud platforms are supported
- Written in Java

#### Usage:
Setup:
1. Add the extension to your instance of Burp by installing directly from the "BApp Store" tab within Burp or by loading the jar file from the Extensions tab.
2. In the "Qualys WAS" tab, select the appropriate Qualys platform for your subscription and enter your Qualys username & password.
3. Click "Validate Credentials" to ensure successful connectivity to the Qualys platform.
4. Review the "Logs" section on the Qualys WAS tab to see API success/failure messages.

To validate a WAS finding:
1. Go to Burp Repeater and right-click in the empty Request area.
2. Select "Import Qualys WAS Finding".
3. Choose "Enter Finding ID" if you know the WAS finding ID, otherwise choose "Select from a Web App's Open Findings". 
4. If you chose 
	- "Enter Finding ID", enter the finding ID in the text box (the longer UUID of the finding is preferred, although the numeric finding ID should work as well). Click "Fetch". 
	- "Select from a Web App's Open Findings", you will see a list of web apps from WAS. Select a web app. The open vulnerabilities will be loaded into the Findings list. Note that only vulnerabilities are loaded, not "informational" QIDs. Select the finding you want to validate. If multiple payloads are present, you will also need to choose one of the payloads. 
5. Click "Import Request". (Note: If the WAS finding was detected prior to WAS Engine 7.0, some request headers may be missing or the format may need to be tweaked manually). 
6. If required, manually update the session cookie or other authentication token in the request.
7. Click "Send" and inspect the response to validate the finding.

To send Burp issues to WAS:
1. Perform passive and/or active scans in Burp.
2. Go to: Target > Site map > Issues.
3. Right-click the desired scanner issue(s) and click "Send to Qualys WAS". 
4. Select the web application from WAS for which the issues apply. If you don't see the correct web app in the list, the web app may not have been created within WAS yet or the Qualys user account entered may not have permission to the correct web app.
5. Select the "purge" or "close" checkbox as desired.
6. Click the "Send to Qualys WAS" button.

#### Changelog:
** 1.0.0 30-Jul-2018
- Initial release

** 2.0.0 30-Sep-2019
- Added support for new Qualys shared platforms: Canada and US4
- Added new feature to import a WAS finding into Repeater

** 2.0.1 20-Sep-2021
- Added support for new Qualys shared platforms: AE1

** 2.0.2 23-Sep-2024
- Fixed issue for Burp Findings Import With Blank Request/Response
