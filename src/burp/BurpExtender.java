package burp;

import burp.exception.PayloadInstanceException;
import burp.exception.UnauthorizedException;
import burp.model.PayloadInstance;
import burp.model.WASFinding;
import burp.model.WebAppItem;

import javax.swing.*;
import javax.swing.border.TitledBorder;
import java.awt.*;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;
import java.awt.font.TextAttribute;
import java.io.File;
import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.net.URI;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.List;
import java.util.*;
import java.util.concurrent.ExecutionException;

public class BurpExtender
        implements IBurpExtender, ITab, IExtensionStateListener, IContextMenuFactory, ActionListener {
    private IBurpExtenderCallbacks callbacks;
    private IScanIssue[] scanIssues = null;
    private JSplitPane splitPane;
    private JTextField username_field;
    private JPasswordField password_field;
    private JTextField username_field_tab = new JTextField(25);
    private JPasswordField password_field_tab = new JPasswordField(25);
    private JComboBox<String> qualysPortal_URI_list_tab;
    private int portalSelectedIndex;

    private String username_login;
    private char[] password_login;

    private JTextField qualys_portal_textfield_onexportPanel;
    private JLabel webAppURLLabel;
    private JComboBox<String> webapplication_list_combox;
    private JComboBox<String> qualysPortal_URI_list;
    private JCheckBox purgeIssues;
    private JCheckBox closeIssues;

    private List<String> webapplistsLabel = new ArrayList<String>();
    private List<String> payloadlistsLabel = new ArrayList<String>();
    private List<String> payloadlistsForWebappsLabel = new ArrayList<String>();
    private List<String> findingslistLabel = new ArrayList<String>();
    private JScrollPane logPane;
    private static JPanel upperPanel;
    private static JPanel lowerPanel;
    public static JTextArea logTextArea = new JTextArea("");

    private JButton refresh;

    private String searchWebappsURL;
    private String importBurpURL;
    private GridBagConstraints constraints;
    private JPanel loginPanel;
    private JPanel buttonsPanel;
    private JPanel exportBurpFilePanel;
    private JPanel importFindingPanel;


    private static JLabel webappid_label = new JLabel("Web App Name (Select the Web application associated with these issues) : ");

    private JLabel authenticationLabel = new JLabel();
    private JLabel authenticationLabelInTab = new JLabel();
    private JLabel exportStatusLabel = new JLabel();
    private JLabel failedExportStatusLabel = new JLabel();

    private JLabel processing;
    private JLabel processingInTab;

    private JTextField pcpURLInTab = new JTextField(25); // private cloud platform
    private JTextField pcpURL;
    private JLabel pcpURLLabelInTab;
    private String qualysPlatformURL;

    private WASSearch wasSearchRequest;
    private ArrayList<WebAppItem> webappLists;
    private ArrayList<PayloadInstance> payloadInstanceList;
    private ArrayList<PayloadInstance> payloadInstanceForWebapps;
    private ArrayList<WASFinding> findingsList;

    public static StringBuilder logBuilder = new StringBuilder();
    private SimpleDateFormat time_formatter = new SimpleDateFormat("yyyy-MM-dd_HH:mm:ss.SSS");

    private static final String PCP = "Private Cloud Platform";

    private int requestCount = 1;

    private static final String[] QUALYS_Portal_Name_List = {"US Platform 1", "US Platform 2", "US Platform 3", "US Platform 4", "EU Platform 1",
            "EU Platform 2", "Canada Platform", "India Platform", PCP};


    private static final String[] QUALYS_PORTAL_URL = {"https://qualysapi.qualys.com",
            "https://qualysapi.qg2.apps.qualys.com",
            "https://qualysapi.qg3.apps.qualys.com",
            "https://qualysapi.qg4.apps.qualys.com",
            "https://qualysapi.qualys.eu",
            "https://qualysapi.qg2.apps.qualys.eu",
            "https://qualysapi.qg1.apps.qualys.ca",
            "https://qualysapi.qg1.apps.qualys.in",
            PCP
    };

    private static final String EXTENSION_NAME = "Qualys WAS";
    private static final String AUTHENTICATION_FAIL_ERROR_MESSAGE = "Authentication Failed or Unauthorized. Please check logs.";
    private static final String EXPORT_XML_FILE_FAIL_ERROR_MESSAGE = "Export to WAS failed. Please check Logs on the Qualys WAS tab for details.";
    private static final String LOGIN_SUCCESSFUL_MESSAGE = "Credentials Validated Successfully!";
    private static final String EMPTY_LOGIN_USERNAME_INPUTFIELD_ERROR_MESSAGE = "Error: Username field is empty, request can not be processed";
    private static final String EMPTY_LOGIN_PASSWORD_INPUTFIELD_ERROR_MESSAGE = "Error: Password field is empty, request can not be processed";
    private static final String EMPTY_PLATFORM_URL_INPUTFIELD_ERROR_MESSAGE = "Error: Qualys API Server base URL field is empty, request can not be processed";
    private static final String PURGE_BURP_ISSUES_TOOLTIP_TEXT = "If option is checked, all previous issues for the web application will be removed before import report issues.\n" +
            "Recommended to avoid duplicate findings when you are importing from multiple Burp instances.";
    private static final String CLOSE_EXISTING_ISSUES_TOOLTIP_TEXT = "If option is checked, existing issues not reported in this report will be marked as Fixed.";
    private static final String PROCESSING = "Processing...";
    private static final String WEB_APP_URL_LABEL = "Web App URL : ";
    private static final String RESOURCES_SPINNER_GIF = "resources/spinner.gif";
    private static final int MAX_FINDINGS = 100;
    private static final String SEND_TO_WAS_TITLE = "Qualys WAS Settings";
    private static final String IMPORT_FROM_WAS_TITLE = "Qualys WAS Import Settings";
    private JFrame frame = new JFrame(SEND_TO_WAS_TITLE);
    private String INVOCATION_CONTEXT = "SendToQualys";

    public BurpExtender() {
        // empty
    }

    public List<JMenuItem> createMenuItems(IContextMenuInvocation invocation) {
        URL url = this.getClass().getClassLoader().getResource("resources/logo.png");
        ImageIcon imgicon = new ImageIcon(url);
        frame.setIconImage(imgicon.getImage());

        ArrayList<JMenuItem> menu = new ArrayList<JMenuItem>();
        byte ctx = invocation.getInvocationContext();
        // Only show context menu for scanner results...
        ImageIcon imageIcon = new ImageIcon(url);
        Image image = imageIcon.getImage(); // transform it
        Image newimg = image.getScaledInstance(13, 20, java.awt.Image.SCALE_SMOOTH); // scale it the smooth way
        imageIcon = new ImageIcon(newimg);  // transform it back

        if (ctx == IContextMenuInvocation.CONTEXT_SCANNER_RESULTS) {
            this.scanIssues = invocation.getSelectedIssues();

            JMenuItem item = new JMenuItem("Send to Qualys WAS", imageIcon);
            INVOCATION_CONTEXT = "SendToQualys";
            item.addActionListener(this);
            menu.add(item);
        }

        if (ctx == IContextMenuInvocation.CONTEXT_MESSAGE_EDITOR_REQUEST) {
            JMenuItem item = new JMenuItem("Import Qualys WAS Finding", imageIcon);
            item.addActionListener(this);
            INVOCATION_CONTEXT = "ImportFromQualys";
            menu.add(item);
        }
        return menu;
    }


    public void actionPerformed(ActionEvent e) {
        if (username_login == null || password_login == null) {
            showLoginWizard();
        } else {
            if (INVOCATION_CONTEXT.equals("SendToQualys")) {
                paintNextPageInWizard(webappLists);
            } else if (INVOCATION_CONTEXT.equals("ImportFromQualys")) {
                paintNextPageInWizardForImportFinding(webappLists);

            }
        }
    }

    public void showLoginWizard() {
        //For context-menu
        frame.setTitle(SEND_TO_WAS_TITLE);
        frame.getContentPane().removeAll();
        frame.setLayout(new FlowLayout());

        loginPanel = new JPanel(new GridBagLayout());
        constraints = new GridBagConstraints();
        constraints.anchor = 17;
        constraints.insets = new Insets(10, 10, 10, 10);

        loginPanel.setPreferredSize(new Dimension(580, 450));

        JLabel username_label = new JLabel("Qualys Username : ");
        JLabel password_label = new JLabel("Qualys Password  : ");
        JLabel qualys_Portal_URL_Label = new JLabel("Qualys Portal Platform URL : ");


        constraints.gridx = 0;
        constraints.gridy = 2;
        qualys_Portal_URL_Label.setForeground(Color.DARK_GRAY);
        qualys_Portal_URL_Label.setFont(new Font(username_label.getFont().getFamily(), 1, 13));
        loginPanel.add(qualys_Portal_URL_Label, constraints);

        qualysPortal_URI_list = new JComboBox<String>(QUALYS_Portal_Name_List);
        qualysPortal_URI_list.setPreferredSize(new Dimension(225, 30));
        constraints.gridx = 1;
        loginPanel.add(qualysPortal_URI_list, constraints);

        JLabel whatsMyPlatform = new JLabel("What's my platform?");
        whatsMyPlatform.setFont(new Font("Courier New", 1, 11));
        Font font = whatsMyPlatform.getFont();
        Map attributes = font.getAttributes();
        attributes.put(TextAttribute.UNDERLINE, TextAttribute.UNDERLINE_ON);
        whatsMyPlatform.setFont(font.deriveFont(attributes));
        whatsMyPlatform.setForeground(Color.blue);
        whatsMyPlatform.setCursor(new Cursor(Cursor.HAND_CURSOR));
        whatsMyPlatform.setMinimumSize(whatsMyPlatform.getPreferredSize());
        whatsMyPlatform.addMouseListener(new MouseAdapter() {
            @Override
            public void mouseClicked(MouseEvent e) {
                try {
                    Desktop.getDesktop().browse(new URI("https://www.qualys.com/platform-identification/"));
                } catch (Exception ex) {
                    //It looks like there's a problem
                }
            }
        });

        constraints.gridx = 1;
        constraints.gridy = 3;
        constraints.anchor = GridBagConstraints.NORTHEAST;
        loginPanel.add(whatsMyPlatform, constraints);

        JLabel pcpURLLabel = new JLabel("Qualys API server base URL : ");
        constraints.gridx = 0;
        constraints.gridy = 4;
        pcpURLLabel.setFont(new Font(username_label.getFont().getFamily(), 1, 13));
        pcpURLLabel.setForeground(Color.DARK_GRAY);
        pcpURL = new JTextField(25);
        pcpURLLabel.setVisible(false);
        pcpURL.setVisible(false);

        loginPanel.add(pcpURLLabel, constraints);

        constraints.gridx = 1;
        loginPanel.add(pcpURL, constraints);


        qualysPortal_URI_list.addActionListener(new ActionListener() {

            @Override
            public void actionPerformed(ActionEvent e) {
                if (qualysPortal_URI_list.getSelectedIndex() != -1) {
                    String url = QUALYS_Portal_Name_List[qualysPortal_URI_list.getSelectedIndex()];
                    if (url.equals(PCP)) {
                        pcpURL.setVisible(true);
                        pcpURLLabel.setVisible(true);
                    } else {
                        pcpURLLabel.setVisible(false);
                        pcpURL.setVisible(false);
                    }
                }

            }
        });

        constraints.gridx = 0;
        constraints.gridy = 5;
        username_label.setFont(new Font(username_label.getFont().getFamily(), 1, 13));
        username_label.setForeground(Color.DARK_GRAY);
        username_field = new JTextField(25);
        loginPanel.add(username_label, constraints);

        constraints.gridx = 1;
        loginPanel.add(username_field, constraints);

        constraints.gridx = 0;
        constraints.gridy = 6;
        password_label.setForeground(Color.DARK_GRAY);
        password_label.setFont(new Font(username_label.getFont().getFamily(), 1, 13));
        password_field = new JPasswordField(25);
        loginPanel.add(password_label, constraints);

        constraints.gridx = 1;
        loginPanel.add(password_field, constraints);

        JButton loginButton = new JButton("Validate Credentials");
        loginButton.addActionListener(new ValidateCredsActionListener(true));
        constraints.gridx = 1;
        constraints.gridy = 7;
        constraints.anchor = GridBagConstraints.WEST;
        loginPanel.add(loginButton, constraints);

        constraints.gridx = 0;
        constraints.gridy = 8;
        URL urlGif = this.getClass().getClassLoader().getResource(RESOURCES_SPINNER_GIF);
        ImageIcon imgiconGif = new ImageIcon(urlGif);
        Image imgGif = imgiconGif.getImage();

        imgiconGif = new ImageIcon(imgGif);
        processing = new JLabel(PROCESSING, imgiconGif, JLabel.CENTER);
        processing.setVisible(false);
        loginPanel.add(processing, constraints);

        constraints.gridx = 0;
        constraints.gridy = 9;
        constraints.gridwidth = GridBagConstraints.REMAINDER;
        authenticationLabel.setVisible(false);
        loginPanel.add(authenticationLabel, constraints);

        TitledBorder loginBorder = new TitledBorder("Login Credentials");
        loginBorder.setTitleJustification(TitledBorder.LEFT);
        loginBorder.setTitlePosition(TitledBorder.TOP);

        loginPanel.setBorder(loginBorder);

        frame.getContentPane().add(loginPanel);

        frame.pack();
        frame.setLocationRelativeTo(upperPanel);
        frame.setVisible(true);
    }


    public void registerExtenderCallbacks(final IBurpExtenderCallbacks callbacks) {
        this.callbacks = callbacks;
        callbacks.setExtensionName(EXTENSION_NAME);
        callbacks.registerContextMenuFactory(this);

        SwingUtilities.invokeLater(new Runnable() {
            public void run() {
                splitPane = new JSplitPane(0);

                int dividerLocation_Vertical = Double.valueOf(0.65 * Toolkit.getDefaultToolkit().getScreenSize().height).intValue();

                splitPane.setDividerLocation(dividerLocation_Vertical);
                upperPanel = new JPanel(new GridBagLayout());
                lowerPanel = new JPanel(new GridLayout(1, 1));

                logPane = new JScrollPane(logTextArea);

                BurpExtender.this.buildLoginPanel();

                BurpExtender.upperPanel.setBorder(BorderFactory.createTitledBorder(BorderFactory.createEtchedBorder(), "Enter Qualys Subscription Details"));
                logPane.setBorder(BorderFactory.createTitledBorder(BorderFactory.createEtchedBorder(), "Logs"));

                splitPane.add(upperPanel);
                splitPane.add(lowerPanel);
                upperPanel.add(loginPanel);
                lowerPanel.add(logPane);

                callbacks.customizeUiComponent(splitPane);
                callbacks.customizeUiComponent(upperPanel);
                callbacks.customizeUiComponent(logPane);
                callbacks.customizeUiComponent(lowerPanel);

                callbacks.addSuiteTab(BurpExtender.this);
            }
        });
    }


    public String getTabCaption() {
        return EXTENSION_NAME;
    }


    public Component getUiComponent() {
        return splitPane;
    }

    private void buildLoginPanel() {
        loginPanel = new JPanel(new GridBagLayout());
        loginPanel.setPreferredSize(new Dimension(535, 400));
        constraints = new GridBagConstraints();
        constraints.anchor = 17;
        constraints.insets = new Insets(10, 10, 10, 10);

        JLabel username_label = new JLabel("Qualys Username  : ");
        JLabel password_label = new JLabel("Qualys Password    : ");
        JLabel qualys_Portal_URL_Label = new JLabel("Qualys Portal Platform : ");

        qualysPortal_URI_list_tab = new JComboBox<String>(QUALYS_Portal_Name_List);

        qualysPortal_URI_list_tab.setPreferredSize(new Dimension(225, 30));

        JButton loginButton = new JButton("Validate Credentials");
        loginButton.addActionListener(new ValidateCredsActionListener(false));

        JButton clearButton = new JButton("Clear Settings ");
        clearButton.addActionListener(new ActionListener() {

            @Override
            public void actionPerformed(ActionEvent e) {
                username_field_tab.setText("");
                password_field_tab.setText("");
                username_login = null;
                password_login = null;
                qualysPlatformURL = null;
                pcpURLInTab.setText("");
                ;
                authenticationLabelInTab.setVisible(false);
                logTextArea.setText("");
                logBuilder.delete(0, logBuilder.length());
                wasSearchRequest = null;
                processingInTab.setVisible(false);

            }
        });

        constraints.gridx = 0;
        constraints.gridy = 2;
        loginPanel.add(qualys_Portal_URL_Label, constraints);
        qualys_Portal_URL_Label.setForeground(Color.DARK_GRAY);
        qualys_Portal_URL_Label.setFont(new Font(username_label.getFont().getFamily(), 1, 13));

        constraints.gridx = 1;
        loginPanel.add(qualysPortal_URI_list_tab, constraints);


        JLabel whatsMyPlatform = new JLabel("What's my platform?");
        whatsMyPlatform.setFont(new Font("Courier New", 1, 11));
        Font font = whatsMyPlatform.getFont();
        Map attributes = font.getAttributes();
        attributes.put(TextAttribute.UNDERLINE, TextAttribute.UNDERLINE_ON);
        whatsMyPlatform.setFont(font.deriveFont(attributes));
        whatsMyPlatform.setForeground(Color.blue);
        whatsMyPlatform.setCursor(new Cursor(Cursor.HAND_CURSOR));
        whatsMyPlatform.setMinimumSize(whatsMyPlatform.getPreferredSize());
        whatsMyPlatform.addMouseListener(new MouseAdapter() {
            @Override
            public void mouseClicked(MouseEvent e) {
                try {
                    Desktop.getDesktop().browse(new URI("https://community.qualys.com/docs/DOC-4172"));
                } catch (Exception ex) {
                    //It looks like there's a problem
                }
            }
        });

        constraints.gridx = 1;
        constraints.gridy = 3;
        constraints.anchor = GridBagConstraints.NORTHEAST;
        loginPanel.add(whatsMyPlatform, constraints);

        pcpURLLabelInTab = new JLabel("Qualys API Server base URL : ");
        constraints.gridx = 0;
        constraints.gridy = 4;
        pcpURLLabelInTab.setFont(new Font(username_label.getFont().getFamily(), 1, 13));
        pcpURLLabelInTab.setForeground(Color.DARK_GRAY);
        pcpURLLabelInTab.setVisible(false);
        pcpURLInTab.setVisible(false);

        loginPanel.add(pcpURLLabelInTab, constraints);

        constraints.gridx = 1;
        loginPanel.add(pcpURLInTab, constraints);


        qualysPortal_URI_list_tab.addActionListener(new ActionListener() {

            @Override
            public void actionPerformed(ActionEvent e) {
                if (qualysPortal_URI_list_tab.getSelectedIndex() != -1) {
                    String url = QUALYS_Portal_Name_List[qualysPortal_URI_list_tab.getSelectedIndex()];
                    if (url.equals(PCP)) {
                        pcpURLInTab.setVisible(true);
                        pcpURLLabelInTab.setVisible(true);
                    } else {
                        pcpURLLabelInTab.setVisible(false);
                        pcpURLInTab.setVisible(false);
                    }
                }

            }
        });


        constraints.gridx = 0;
        constraints.gridy = 5;

        username_label.setFont(new Font(username_label.getFont().getFamily(), 1, 13));
        username_label.setForeground(Color.DARK_GRAY);
        loginPanel.add(username_label, constraints);

        username_field_tab.setMinimumSize(new Dimension(username_field_tab.getPreferredSize().width - 5, username_field_tab.getPreferredSize().height - 5));
        password_field_tab.setMinimumSize(new Dimension(password_field_tab.getPreferredSize().width - 5, password_field_tab.getPreferredSize().height - 5));
        pcpURLInTab.setMinimumSize(new Dimension(pcpURLInTab.getPreferredSize().width - 5, pcpURLInTab.getPreferredSize().height - 5));

        constraints.gridx = 1;
        loginPanel.add(username_field_tab, constraints);

        constraints.gridx = 0;
        constraints.gridy = 6;
        loginPanel.add(password_label, constraints);
        password_label.setForeground(Color.DARK_GRAY);
        password_label.setFont(new Font(username_label.getFont().getFamily(), 1, 13));


        constraints.gridx = 1;
        loginPanel.add(password_field_tab, constraints);


        constraints.gridx = 1;
        constraints.gridy = 7;
        constraints.anchor = GridBagConstraints.WEST;
        loginPanel.add(loginButton, constraints);

        constraints.gridx = 0;
        constraints.gridy = 7;
        constraints.anchor = GridBagConstraints.EAST;
        loginPanel.add(clearButton, constraints);

        constraints.anchor = GridBagConstraints.CENTER;

        URL urlGif = this.getClass().getClassLoader().getResource(RESOURCES_SPINNER_GIF);
        ImageIcon imgiconGif = new ImageIcon(urlGif);
        Image imgGif = imgiconGif.getImage();

        imgiconGif = new ImageIcon(imgGif);
        processingInTab = new JLabel(PROCESSING, imgiconGif, JLabel.CENTER);


        constraints.gridx = 0;
        constraints.gridy = 8;
        constraints.gridwidth = GridBagConstraints.REMAINDER;
        processingInTab.setVisible(false);
        loginPanel.add(processingInTab, constraints);

        constraints.gridx = 0;
        constraints.gridy = 9;
        constraints.gridwidth = GridBagConstraints.REMAINDER;
        authenticationLabelInTab.setVisible(false);
        loginPanel.add(authenticationLabelInTab, constraints);

        TitledBorder loginBorder = new TitledBorder("Login Credentials");
        loginBorder.setTitleJustification(TitledBorder.LEFT);
        loginBorder.setTitlePosition(TitledBorder.TOP);

        loginPanel.setBorder(loginBorder);

    }

    private void buildConfigPanel() {

        frame.setTitle(SEND_TO_WAS_TITLE);
        frame.setLayout(new GridBagLayout());
        exportBurpFilePanel = new JPanel(new GridBagLayout());
        exportBurpFilePanel.setPreferredSize(new Dimension(590, 400));
        constraints = new GridBagConstraints();
        constraints.anchor = 17;
        constraints.insets = new Insets(10, 10, 10, 10);


        webapplication_list_combox = new JComboBox<String>();
        webapplication_list_combox.setFont(new Font(webappid_label.getFont().getFamily(), 0, 12));
        webapplication_list_combox.setPreferredSize(new Dimension(360, 25));
        webapplication_list_combox.setAutoscrolls(true);

        qualys_portal_textfield_onexportPanel = new JTextField(39);
        qualys_portal_textfield_onexportPanel.setMinimumSize(qualys_portal_textfield_onexportPanel.getPreferredSize());

        if (QUALYS_Portal_Name_List[portalSelectedIndex].equals(PCP)) {
            qualys_portal_textfield_onexportPanel.setText(QUALYS_Portal_Name_List[portalSelectedIndex] + " - " + qualysPlatformURL);
        } else {
            qualys_portal_textfield_onexportPanel.setText(QUALYS_Portal_Name_List[portalSelectedIndex]);
        }
        qualys_portal_textfield_onexportPanel.setEditable(false);
        JButton sendButton = new JButton("Send to Qualys WAS ");
        sendButton.setFont(new Font(webappid_label.getFont().getFamily(), 1, 10));
        sendButton.addActionListener(new ExportFileButtonActionListener());


        JLabel qualys_Portal_URL_Label = new JLabel("Qualys Portal Platform : ");
        constraints.gridx = 0;
        constraints.gridy = 0;
        qualys_Portal_URL_Label.setForeground(Color.DARK_GRAY);
        qualys_Portal_URL_Label.setFont(new Font(webappid_label.getFont().getFamily(), 1, 12));
        exportBurpFilePanel.add(qualys_Portal_URL_Label, constraints);

        constraints.gridx = 0;
        constraints.gridy = 1;
        qualys_portal_textfield_onexportPanel.setVisible(true);
        exportBurpFilePanel.add(qualys_portal_textfield_onexportPanel, constraints);

        constraints.gridx = 0;
        constraints.gridy = 2;
        constraints.weightx = 1;

        constraints.anchor = GridBagConstraints.FIRST_LINE_START;
        webappid_label.setForeground(Color.DARK_GRAY);
        webappid_label.setFont(new Font(webappid_label.getFont().getFamily(), 1, 12));
        exportBurpFilePanel.add(webappid_label, constraints);


        constraints.gridx = 0;
        constraints.gridy = 3;

        refresh = new JButton();
        URL url = this.getClass().getClassLoader().getResource("resources/refresh.png");
        ImageIcon imgicon = new ImageIcon(url);
        Image img = imgicon.getImage();
        Image newimg = img.getScaledInstance(15, 15, java.awt.Image.SCALE_SMOOTH);
        imgicon = new ImageIcon(newimg);
        refresh.setIcon(imgicon);

        refresh.addActionListener(new ActionListener() {

            @Override
            public void actionPerformed(ActionEvent e) {
                refreshWebAppsList();

            }
        });

        constraints.anchor = GridBagConstraints.FIRST_LINE_START;

        JPanel webAppRefresh = new JPanel(new FlowLayout(FlowLayout.LEFT));
        webAppRefresh.setPreferredSize(new Dimension(450, 30));
        webAppRefresh.add(webapplication_list_combox);
        webAppRefresh.add(refresh);

        exportBurpFilePanel.add(webAppRefresh, constraints);

        webAppURLLabel = new JLabel();
        webAppURLLabel.setMinimumSize(webAppURLLabel.getPreferredSize());
        webAppURLLabel.setFont(new Font(webappid_label.getFont().getFamily(), 0, 11));

        constraints.gridx = 0;
        constraints.gridy = 4;
        constraints.weightx = 1;
        constraints.gridwidth = 2;
        constraints.anchor = GridBagConstraints.FIRST_LINE_START;
        exportBurpFilePanel.add(webAppURLLabel, constraints);

        constraints.gridx = 0;
        constraints.gridy = 5;
        constraints.weightx = 1;
        constraints.anchor = GridBagConstraints.FIRST_LINE_START;
        constraints.gridwidth = 2;
        purgeIssues = new JCheckBox("Purge web application Burp issues before import.");
        purgeIssues.setFont(new Font(webappid_label.getFont().getFamily(), 1, 12));
        purgeIssues.setToolTipText(PURGE_BURP_ISSUES_TOOLTIP_TEXT);
        exportBurpFilePanel.add(purgeIssues, constraints);

        constraints.gridy = 6;
        closeIssues = new JCheckBox("Close existing issues not reported anymore.");
        closeIssues.setToolTipText(CLOSE_EXISTING_ISSUES_TOOLTIP_TEXT);
        closeIssues.setFont(new Font(webappid_label.getFont().getFamily(), 1, 12));
        exportBurpFilePanel.add(closeIssues, constraints);

        TitledBorder border = new TitledBorder("Send Burp issues to Qualys WAS");
        border.setTitleJustification(TitledBorder.LEFT);
        border.setTitlePosition(TitledBorder.TOP);
        exportBurpFilePanel.setBorder(border);

        constraints.gridx = 0;
        constraints.gridy = 7;
        URL urlGif = this.getClass().getClassLoader().getResource(RESOURCES_SPINNER_GIF);
        ImageIcon imgiconGif = new ImageIcon(urlGif);
        Image imgGif = imgiconGif.getImage();

        imgiconGif = new ImageIcon(imgGif);
        processing = new JLabel(PROCESSING, imgiconGif, JLabel.CENTER);
        processing.setVisible(false);
        exportBurpFilePanel.add(processing, constraints);

        buttonsPanel = new JPanel();

        constraints.anchor = GridBagConstraints.PAGE_END; //bottom of space
        constraints.gridwidth = 2;   //2 columns wide
        buttonsPanel.add(sendButton);

        JButton closeButton = new JButton("Close");
        closeButton.setFont(new Font(webappid_label.getFont().getFamily(), 1, 10));
        closeButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent e) {
                frame.dispose();
            }
        });

        constraints.anchor = GridBagConstraints.WEST;
        buttonsPanel.add(closeButton);

        constraints.gridx = 0;
        constraints.gridy = 8;
        exportStatusLabel.setVisible(false);
        exportBurpFilePanel.add(exportStatusLabel, constraints);

        constraints.gridx = 0;
        constraints.gridy = 9;
        failedExportStatusLabel.setVisible(false);
        exportBurpFilePanel.add(failedExportStatusLabel, constraints);


        exportBurpFilePanel.repaint();

        constraints.gridx = 0;
        constraints.gridy = 0;
        constraints.weightx = 1;
        constraints.anchor = GridBagConstraints.NORTH;
        frame.getContentPane().add(exportBurpFilePanel, constraints);

        constraints.gridy = 1;
        constraints.anchor = GridBagConstraints.SOUTH;
        frame.getContentPane().add(buttonsPanel, constraints);
        frame.pack();
        frame.setLocationRelativeTo(upperPanel);
        frame.setVisible(true);

    }


    // --------   Import WAS Detection Panel components -------------
    private JPanel findingsRadioPanel;
    private JRadioButton findingIdRadio;
    private JRadioButton webappsRadio;
    private JPanel findingIdPanel;
    private JLabel findingIdLabel;
    private JTextField findingIdTextField;
    private JLabel findingIdRequest;
    private JComboBox<String> findingIdRequestCombo;

    private JPanel webappsPanel;
    private JLabel webappsLabel;
    private JComboBox<String> webappsCombo;
    private JLabel findingsLabel;
    private JComboBox<String> findingsCombo;
    private JLabel requestPayloadLabel;
    private JComboBox<String> requestPayloadCombo;
    private JButton importButton;
    private JButton fetchButton;
    private ButtonGroup group;
    private JLabel processingSpinner;
    private JLabel findingIdRequestDetails;
    private JLabel webappsFindingRequestDetails;
    private JPanel buttonPanel;
    private ArrayList<String> webappsWithNone = new ArrayList<String>();
    private ComboboxToolTipRenderer findingsRenderer;
    private ComboboxToolTipRenderer payloadsRenderer;
    private ComboboxToolTipRenderer webappsPayloadRenderer;

    private void initImportWASDetectionPanelComponents() {

        frame.setTitle(IMPORT_FROM_WAS_TITLE);
        if (importFindingPanel != null) {
            importFindingPanel.repaint();
            frame.getContentPane().add(importFindingPanel);
            frame.pack();
            frame.setLocationRelativeTo(upperPanel);
            frame.setVisible(true);
            return;
        }

        findingsRadioPanel = new JPanel();
        findingIdRadio = new JRadioButton();
        webappsRadio = new JRadioButton();
        findingIdPanel = new JPanel();
        findingIdLabel = new JLabel();
        findingIdRequestDetails = new JLabel();
        webappsFindingRequestDetails = new JLabel();
        findingIdTextField = new JTextField();
        findingIdRequest = new JLabel();
        findingIdRequestCombo = new JComboBox<String>();
        webappsPanel = new JPanel();
        webappsLabel = new JLabel();
        webappsCombo = new JComboBox<String>();
        findingsLabel = new JLabel();
        findingsCombo = new JComboBox<String>();
        requestPayloadLabel = new JLabel();
        requestPayloadCombo = new JComboBox<String>();
        importButton = new JButton();
        fetchButton = new JButton();
        group = new ButtonGroup();
        buttonPanel = new JPanel();


        URL urlGif = this.getClass().getClassLoader().getResource(RESOURCES_SPINNER_GIF);
        ImageIcon imgiconGif = new ImageIcon(urlGif);
        Image imgGif = imgiconGif.getImage();

        imgiconGif = new ImageIcon(imgGif);
        processingSpinner = new JLabel(PROCESSING, imgiconGif, JLabel.CENTER);
        processingSpinner.setVisible(false);

        //======== panel1 ========
        {

            TitledBorder findingsBorder = new TitledBorder("Import Options");
            findingsBorder.setTitleJustification(TitledBorder.LEFT);
            findingsBorder.setTitlePosition(TitledBorder.TOP);

            findingsRadioPanel.setBorder(findingsBorder);

            findingsRadioPanel.setLayout(new GridLayout(2, 2));
            //---- radioButton2 ----
            findingIdRadio.setText("Enter Finding ID");
            findingsRadioPanel.add(findingIdRadio);
            findingIdRadio.setFont(new Font(findingIdRadio.getFont().getFamily(), 1, 12));

            //---- radioButton3 ----
            webappsRadio.setText("Select from a Web App's Open Findings");
            webappsRadio.setFont(new Font(webappsRadio.getFont().getFamily(), 1, 12));
            group.add(findingIdRadio);
            group.add(webappsRadio);

            findingsRadioPanel.add(webappsRadio);

            findingIdRadio.addActionListener(new ActionListener() {

                @Override
                public void actionPerformed(ActionEvent e) {
                    webappsPanel.setVisible(false);
                    findingIdPanel.setVisible(true);

                }
            });

            webappsRadio.addActionListener(new ActionListener() {

                @Override
                public void actionPerformed(ActionEvent e) {
                    webappsPanel.setVisible(true);
                    findingIdPanel.setVisible(false);
                }
            });
        }


        //======== panel2 ========
        {

            findingIdPanel.setLayout(new GridBagLayout());

            findingIdLabel.setText("Finding ID :  ");
            findingIdLabel.setFont(new Font(findingIdLabel.getFont().getFamily(), 1, 12));
            findingIdPanel.add(findingIdLabel, new GridBagConstraints(0, 1, 1, 1, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 0, 0), 0, 5));
            findingIdTextField.setFont(new Font(findingIdTextField.getFont().getFamily(), 1, 12));
            findingIdPanel.add(findingIdTextField, new GridBagConstraints(3, 1, 5, 1, 3.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 0, 0), 0, 5));

            fetchButton.setText("Fetch");
            fetchButton.setFont(new Font(fetchButton.getFont().getFamily(), 1, 12));
            findingIdPanel.add(fetchButton, new GridBagConstraints(8, 1, 2, 1, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 0, 0), 0, 0));

            findingIdRequestDetails.setText("");
            findingIdRequestDetails.setFont(new Font(findingIdRequestDetails.getFont().getFamily(), Font.ITALIC, 13));
            findingIdRequestDetails.setForeground(Color.DARK_GRAY);
            findingIdPanel.add(findingIdRequestDetails, new GridBagConstraints(0, 2, 11, 2, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 0, 0), 0, 0));

            findingIdRequest.setText("Request Payloads :  ");
            findingIdRequest.setFont(new Font(findingIdRequest.getFont().getFamily(), 1, 12));
            findingIdPanel.add(findingIdRequest, new GridBagConstraints(0, 4, 2, 1, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 0, 0), 0, 0));
            findingIdPanel.add(findingIdRequestCombo, new GridBagConstraints(3, 4, 8, 1, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 0, 0), 0, 0));
            findingIdRequestCombo.setFont(new Font(findingIdRequestCombo.getFont().getFamily(), 1, 12));
            payloadsRenderer = new ComboboxToolTipRenderer();
            findingIdRequestCombo.setRenderer(payloadsRenderer);


            findingIdRequest.setVisible(false);
            findingIdRequestCombo.setVisible(false);
            findingIdRadio.setSelected(true);

            findingIdPanel.add(processingSpinner, new GridBagConstraints(3, 4, 5, 1, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 0, 0), 0, 0));

            fetchButton.addActionListener(new GetFindingDetailsActionListener());

        }

        //======== panel3 ========
        {
            webappsPanel.setLayout(new GridBagLayout());


            //---- Combo 1 ----
            webappsLabel.setText("Web Apps : ");
            webappsLabel.setFont(new Font(webappsLabel.getFont().getFamily(), 1, 12));
            webappsPanel.add(webappsLabel, new GridBagConstraints(0, 0, 2, 1, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 2, 2), 0, 2));
            webappsPanel.add(webappsCombo, new GridBagConstraints(3, 0, 1, 1, 3.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 2, 0), 0, 2));
            webappsCombo.setFont(new Font(webappsCombo.getFont().getFamily(), 1, 12));

            webappsWithNone.clear();
            webappsWithNone.add(0, "--- Select a web app ---");
            for (int counter = 0; counter < webappLists.size(); counter++) {
                WebAppItem webappItem = (WebAppItem) webappLists.get(counter);
                String webappName = webappItem.getWebAppItem_Name();
                webappsWithNone.add(webappName);
            }
            DefaultComboBoxModel<String> webList_model = new DefaultComboBoxModel<String>(webappsWithNone.toArray(new String[0]));
            webappsCombo.setModel(webList_model);
            webappsCombo.addActionListener(new WebAppFindingsActionListener());


            //---- Combo 2 ----
            findingsLabel.setText("Findings : ");
            findingsLabel.setFont(new Font(findingsLabel.getFont().getFamily(), 1, 12));
            webappsPanel.add(findingsLabel, new GridBagConstraints(0, 2, 1, 1, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 2, 2), 0, 2));
            webappsPanel.add(findingsCombo, new GridBagConstraints(3, 2, 1, 1, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 2, 0), 0, 2));
            findingsCombo.setFont(new Font(findingsCombo.getFont().getFamily(), 1, 12));
            findingsCombo.addActionListener(new GetFindingDetailsActionListener());
            findingsRenderer = new ComboboxToolTipRenderer();
            findingsCombo.setRenderer(findingsRenderer);

            //---- Combo 3 ----

            webappsFindingRequestDetails.setText("");
            webappsFindingRequestDetails.setFont(new Font(webappsFindingRequestDetails.getFont().getFamily(), Font.ITALIC, 13));
            webappsFindingRequestDetails.setForeground(Color.DARK_GRAY);
            webappsPanel.add(webappsFindingRequestDetails, new GridBagConstraints(0, 4, 5, 2, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 0, 2), 0, 2));


            requestPayloadLabel.setText("Request Payloads : ");
            requestPayloadLabel.setFont(new Font(requestPayloadLabel.getFont().getFamily(), 1, 12));
            webappsPanel.add(requestPayloadLabel, new GridBagConstraints(0, 6, 1, 1, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 0, 2), 0, 2));
            webappsPanel.add(requestPayloadCombo, new GridBagConstraints(3, 6, 1, 1, 0.0, 0.0,
                    GridBagConstraints.CENTER, GridBagConstraints.BOTH,
                    new Insets(0, 0, 0, 0), 0, 2));
            requestPayloadCombo.setFont(new Font(requestPayloadCombo.getFont().getFamily(), 1, 12));
            webappsPayloadRenderer = new ComboboxToolTipRenderer();
            requestPayloadCombo.setRenderer(webappsPayloadRenderer);

            requestPayloadLabel.setVisible(false);
            requestPayloadCombo.setVisible(false);
            webappsPanel.setVisible(false);
        }

        {
            //---- Import  button ----
            buttonPanel.setLayout(new FlowLayout(FlowLayout.CENTER, 7, 7));
            importButton.setText("Import Request");
            importButton.setFont(new Font(importButton.getFont().getFamily(), 1, 12));
            importButton.addActionListener(new ImportWASDetectionListener());
            buttonPanel.add(importButton);

            // ------ Close button ----
            JButton closeButton = new JButton("Close");
            closeButton.setFont(new Font(closeButton.getFont().getFamily(), 1, 12));
            closeButton.addActionListener(new ActionListener() {
                public void actionPerformed(ActionEvent e) {
                    frame.dispose();
                }
            });
            buttonPanel.add(closeButton);
        }

        frame.setLayout(new FlowLayout(FlowLayout.LEFT));
        importFindingPanel = new JPanel();
        importFindingPanel.setLayout(new BoxLayout(importFindingPanel, BoxLayout.Y_AXIS));
        importFindingPanel.setPreferredSize(new Dimension(590, 400));

        TitledBorder findingsBorder = new TitledBorder("importFindingPanel");
        findingsBorder.setTitleJustification(TitledBorder.LEFT);
        findingsBorder.setTitlePosition(TitledBorder.TOP);
		
      /*findingsRadioPanel.setPreferredSize(new Dimension(150, 100));
      findingIdPanel.setPreferredSize(new Dimension(200, 100));
      webappsPanel.setPreferredSize(new Dimension(200, 150));*/

        findingsRadioPanel.setMaximumSize(new Dimension(450, 100));
        findingIdPanel.setMaximumSize(new Dimension(450, 200));
        webappsPanel.setMaximumSize(new Dimension(450, 220));
        buttonPanel.setMaximumSize(new Dimension(450, 70));

        importFindingPanel.add(findingsRadioPanel);
        importFindingPanel.add(findingIdPanel);
        importFindingPanel.add(webappsPanel);
        importFindingPanel.add(processingSpinner);
        importFindingPanel.add(buttonPanel);

        importFindingPanel.repaint();
        frame.getContentPane().add(importFindingPanel);
        frame.pack();
        frame.setLocationRelativeTo(upperPanel);
        frame.setVisible(true);

    }


    public class ComboboxToolTipRenderer extends DefaultListCellRenderer {
        List<String> tooltips;

        @Override
        public Component getListCellRendererComponent(JList list, Object value,
                                                      int index, boolean isSelected, boolean cellHasFocus) {

            JComponent comp = (JComponent) super.getListCellRendererComponent(list,
                    value, index, isSelected, cellHasFocus);

            if (-1 < index && null != value && null != tooltips) {
                list.setToolTipText(tooltips.get(index));
            }
            return comp;
        }

        public void setTooltips(List<String> tooltips) {
            this.tooltips = tooltips;
        }
    }

    private void refreshWebAppsList() {
        if (wasSearchRequest == null) {
            logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Cannot initiate the request... Please Validate the credentials again. \n");
            logTextArea.setText(logBuilder.toString());
            return;
        }

        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Refreshing WebApps list for given platform... \n");
        logTextArea.setText(logBuilder.toString());

        SwingWorker<String, Integer> worker = new SwingWorker<String, Integer>() {
            @Override
            protected String doInBackground() throws Exception {
                exportStatusLabel.setVisible(false);
                failedExportStatusLabel.setVisible(false);
                processing.setVisible(true);
                return wasSearchRequest.getWebApplicationList();
            }

            // Can safely update the GUI from this method.
            protected void done() {

                String response;
                try {
                    // Retrieve the return value of doInBackground.
                    response = get();
                    if (wasSearchRequest.checkAuthenticationStatus(response)) {
                        webappLists = wasSearchRequest.parseWebApplications(response);
                    }
                    processing.setVisible(false);
                    if (webappLists.isEmpty()) {
                        return;
                    }
                    paintNextPageInWizard(webappLists);
                    WebAppItem webAppItem = webappLists.get(0);  // by default first item selected after refresh
                    webAppURLLabel.setText(WEB_APP_URL_LABEL + webAppItem.getWebAppItem_URL());

                } catch (InterruptedException e) {
                    logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error occurred refreshing webapps; " + e.getMessage() + "\n");
                    logTextArea.setText(logBuilder.toString());
                } catch (ExecutionException e) {
                    logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error occurred refreshing webapps; " + e.getMessage() + "\n");
                    logTextArea.setText(logBuilder.toString());
                }
            }

            @Override

            protected void process(List<Integer> chunks) {
                // Can safely update the GUI from this method.
            }
        };

        worker.execute();

    }

    public void paintNextPageInWizard(ArrayList<WebAppItem> webappLists) {
        if (webappLists == null) {
            return;
        }
        frame.getContentPane().removeAll();

        buildConfigPanel();
        webapplistsLabel.clear();
        for (int counter = 0; counter < webappLists.size(); counter++) {
            WebAppItem webappItem = (WebAppItem) webappLists.get(counter);
            String webappName = webappItem.getWebAppItem_Name();
            webapplistsLabel.add(webappName);
        }

        DefaultComboBoxModel<String> webList_model = new DefaultComboBoxModel<String>(webapplistsLabel.toArray(new String[0]));
        webapplication_list_combox.setModel(webList_model);

        webapplication_list_combox.addActionListener(new ActionListener() {

            @Override
            public void actionPerformed(ActionEvent e) {
                if (webapplication_list_combox.getSelectedIndex() != -1) {
                    WebAppItem webAppItem = webappLists.get(webapplication_list_combox.getSelectedIndex());
                    webAppURLLabel.setText(WEB_APP_URL_LABEL + webAppItem.getWebAppItem_URL());
                }
            }
        });

        WebAppItem webAppItem = webappLists.get(webapplication_list_combox.getSelectedIndex());
        webAppURLLabel.setText(WEB_APP_URL_LABEL + webAppItem.getWebAppItem_URL());

        frame.getContentPane().add(exportBurpFilePanel);
        frame.getContentPane().repaint();
    }


    public void paintNextPageInWizardForImportFinding(ArrayList<WebAppItem> webappLists) {
        if (webappLists == null) {
            return;
        }
        frame.getContentPane().removeAll();

        initImportWASDetectionPanelComponents();

        frame.getContentPane().add(importFindingPanel);
        frame.getContentPane().repaint();
    }

    private String parseIHTTPService(IScanIssue issue) {
        IHttpService ihttpService = issue.getHttpService();
        String http_protocol = ihttpService.getProtocol();
        String http_host = ihttpService.getHost();
        String http_site_map_root = "";
        int http_port = ihttpService.getPort();
        if ((http_port == 80) || (http_port == 443)) {
            http_site_map_root = http_protocol + "://" + http_host + "/";
        } else {
            http_site_map_root = http_protocol + "://" + http_host + ":" + http_port + "/";
        }
        return http_site_map_root;
    }


    public class GetFindingDetailsActionListener implements ActionListener {
        public GetFindingDetailsActionListener() {
        }

        @Override
        public void actionPerformed(ActionEvent e) {

            SwingWorker<String, Integer> worker = new SwingWorker<String, Integer>() {

                @Override
                protected String doInBackground() throws Exception {

                    if (findingIdRadio.isSelected()) {
                        String findingId = findingIdTextField.getText().trim();
                        processingSpinner.setVisible(true);
                        DefaultComboBoxModel<String> empty_model = new DefaultComboBoxModel<String>();
                        findingIdRequestCombo.setModel(empty_model);   //empty the next drop down before painting the api response
                        findingIdRequest.setVisible(false);
                        findingIdRequestCombo.setVisible(false);
                        findingIdRequestDetails.setText("");
                        return wasSearchRequest.getFindingDetails(findingId);
                    } else if (webappsRadio.isSelected()) {
                        int index = findingsCombo.getSelectedIndex();
                        if (index > 0) {
                            WASFinding finding = findingsList.get(index - 1);  //index-1 because first entry is ---select--- entry
                            processingSpinner.setVisible(true);
                            DefaultComboBoxModel<String> empty_model = new DefaultComboBoxModel<String>();
                            requestPayloadCombo.setModel(empty_model);
                            requestPayloadLabel.setVisible(false);
                            requestPayloadCombo.setVisible(false);
                            webappsFindingRequestDetails.setText("");
                            return wasSearchRequest.getFindingDetails(finding.getFindingId());
                        }
                    }
                    return null;

                }

                protected void done() {
                    try {

                        if (findingIdRadio.isSelected()) {
                            String response = get();
                            payloadlistsLabel.clear();
                            processingSpinner.setVisible(false);
                            try {
                                payloadInstanceList = wasSearchRequest.parsePayloadInstance(response);
                            } catch (PayloadInstanceException e) {
                                JOptionPane.showMessageDialog(frame, "Unable to import finding. Only finding type of QUALYS is supported", "Import Error", JOptionPane.ERROR_MESSAGE);
                                if (payloadInstanceList != null) {
                                    payloadInstanceList.clear();
                                }
                                StringWriter sw = new StringWriter();
                                e.printStackTrace(new PrintWriter(sw));
                                String stackTrace = sw.toString();
                                logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Import Error : Unable to import finding. Only finding type of QUALYS is supported " + e.getMessage() + "\n" + stackTrace + "\n");
                                return;
                            } catch (UnauthorizedException e) {
                                findingIdRequestDetails.setText(e.getMessage());
                                if (payloadInstanceList != null) {
                                    payloadInstanceList.clear();
                                }
                                StringWriter sw = new StringWriter();
                                e.printStackTrace(new PrintWriter(sw));
                                String stackTrace = sw.toString();
                                logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Unable to import finding. Unauthorized " + e.getMessage() + "\n" + stackTrace + "\n");
                                return;
                            }

                            int payloadSize = payloadInstanceList.size();
                            logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Payload instances :" + payloadSize + "\n");
                            logTextArea.setText(logBuilder.toString());

                            if (payloadSize == 0) {
                                findingIdRequestDetails.setText("No Payload instance found for this Finding ID.");
                            }

                            if (payloadSize > 0) {
                                PayloadInstance firstPayloadInstance = payloadInstanceList.get(0);
                                String staticText = String.format("<html><br> QID  %s  -  %s <br> %s  %s <br<br> </html>", firstPayloadInstance.getQid(),
                                        firstPayloadInstance.getName(), firstPayloadInstance.getMethod(), firstPayloadInstance.getLink());
                                findingIdRequestDetails.setText(staticText);
                            }

                            if (payloadSize > 1) {
                                for (PayloadInstance p : payloadInstanceList) {
                                    URL url = new URL(p.getLink());
                                    if (p.getMethod().equalsIgnoreCase("POST")) {
                                        //check for payload first, if its missing or N/A then use url query, if query is null, use url path to populate
                                        payloadlistsLabel.add((p.getPayload().equalsIgnoreCase("N/A") || p.getPayload().isEmpty()) ? (url.getQuery() == null ? url.getPath() : url.getQuery()) : p.getPayload());
                                    } else if (p.getMethod().equalsIgnoreCase("GET")) {
                                        payloadlistsLabel.add(url.getQuery() == null ? url.getPath() : url.getQuery());
                                    }
                                }

                                payloadlistsLabel.add(0, "--- Select the Request Payload ---");
                                DefaultComboBoxModel<String> payloadInstance_model = new DefaultComboBoxModel<String>(payloadlistsLabel.toArray(new String[0]));
                                findingIdRequestCombo.setModel(payloadInstance_model);
                                payloadsRenderer.setTooltips(payloadlistsLabel);
                                findingIdRequest.setVisible(true);
                                findingIdRequestCombo.setVisible(true);
                                findingIdRequestCombo.repaint();
                            }

                        } else if (webappsRadio.isSelected()) {
                            String response = get();
                            payloadlistsForWebappsLabel.clear();
                            processingSpinner.setVisible(false);
                            payloadInstanceForWebapps = wasSearchRequest.parsePayloadInstance(response);

                            int payloadSizeForWebapps = payloadInstanceForWebapps.size();
                            logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Payload instances : " + payloadSizeForWebapps + "\n");
                            logTextArea.setText(logBuilder.toString());

                            if (payloadSizeForWebapps == 0) {
                                webappsFindingRequestDetails.setText("No Payload instance found for this Finding ID.");
                            }

                            if (payloadSizeForWebapps > 0) {
                                PayloadInstance firstPayloadInstance = payloadInstanceForWebapps.get(0);
                                String staticText = String.format("<html><br> QID  %s  -  %s <br> %s  %s <br<br> </html>", firstPayloadInstance.getQid(),
                                        firstPayloadInstance.getName(), firstPayloadInstance.getMethod(), firstPayloadInstance.getLink());
                                webappsFindingRequestDetails.setText(staticText);
                            }

                            if (payloadSizeForWebapps > 1) {
                                for (PayloadInstance p : payloadInstanceForWebapps) {
                                    URL url = new URL(p.getLink());
                                    if (p.getMethod().equalsIgnoreCase("POST")) {
                                        payloadlistsForWebappsLabel.add((p.getPayload().equalsIgnoreCase("N/A") || p.getPayload().isEmpty()) ? (url.getQuery() == null ? url.getPath() : url.getQuery()) : p.getPayload());
                                    } else if (p.getMethod().equalsIgnoreCase("GET")) {
                                        payloadlistsForWebappsLabel.add(url.getQuery() == null ? url.getPath() : url.getQuery());
                                    }
                                }

                                payloadlistsForWebappsLabel.add(0, "--- Select the Request Payload ---");
                                DefaultComboBoxModel<String> payloadInstance_model = new DefaultComboBoxModel<String>(payloadlistsForWebappsLabel.toArray(new String[0]));
                                requestPayloadCombo.setModel(payloadInstance_model);
                                webappsPayloadRenderer.setTooltips(payloadlistsForWebappsLabel);
                                requestPayloadLabel.setVisible(true);
                                requestPayloadCombo.setVisible(true);
                                requestPayloadCombo.repaint();
                            }
                        }


                    } catch (Exception e) {
                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Exception parsing payloadInstances : " + e.getMessage() + "\n");
                        logTextArea.setText(logBuilder.toString());
                    }

                }
            };
            worker.execute();

        }

    }

    public class WebAppFindingsActionListener implements ActionListener {

        @Override
        public void actionPerformed(ActionEvent e) {
            SwingWorker<String, Integer> worker = new SwingWorker<String, Integer>() {

                @Override
                protected String doInBackground() throws Exception {
                    int index = webappsCombo.getSelectedIndex();
                    processingSpinner.setVisible(true);
                    DefaultComboBoxModel<String> empty_model = new DefaultComboBoxModel<String>();
                    findingsCombo.setModel(empty_model);
                    requestPayloadCombo.setModel(empty_model);
                    requestPayloadCombo.setVisible(false);
                    requestPayloadLabel.setVisible(false);
                    webappsFindingRequestDetails.setText("");
                    if (index > 0) {
                        WebAppItem webAppItem = webappLists.get(index - 1);
                        return wasSearchRequest.searchFindings(webAppItem.getWebAppItem_ID());
                    }
                    return null;
                }

                protected void done() {
                    try {
                        String response = get();
                        processingSpinner.setVisible(false);
                        findingsList = wasSearchRequest.parseFindings(response);

                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Total number of findings in this API response : " + findingsList.size() + "\n");
                        logTextArea.setText(logBuilder.toString());

                        findingslistLabel.clear();

                        if (findingsList.size() == 0) {
                            webappsFindingRequestDetails.setText("No findings are available for the selected web app.");
                            return;
                        }

                        for (WASFinding p : findingsList) {
                            findingslistLabel.add(p.toString());
                        }

                        findingslistLabel.add(0, "--- Select the Finding ---");
                        DefaultComboBoxModel<String> finding_model = new DefaultComboBoxModel<String>(findingslistLabel.toArray(new String[0]));
                        findingsCombo.setModel(finding_model);
                        findingsRenderer.setTooltips(findingslistLabel);
                        processingSpinner.setVisible(false);
                        findingsCombo.repaint();

                        if (findingsList.size() == MAX_FINDINGS) {
                            if (wasSearchRequest.hasMoreRecords(response)) {
                                webappsFindingRequestDetails.setText("<html>NOTE: More than 100 open findings were found for this web app.<br> Only 100 are listed here. You can enter finding ID as an alternative.</html>");
                            }
                        }

                    } catch (Exception e) {
                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Exception parsing WAS findings : " + e.getMessage() + "\n");
                        logTextArea.setText(logBuilder.toString());
                    }

                }
            };
            worker.execute();
        }


    }

    public class ExportFileButtonActionListener implements ActionListener {
        public ExportFileButtonActionListener() {
        }

        public void actionPerformed(ActionEvent e) {

            SwingWorker<String, Integer> worker = new SwingWorker<String, Integer>() {
                WASImport wasImportRequest;

                // Aggregated state for multi-host grouped imports.
                // Marker value returned by doInBackground() when aggregated mode is in effect.
                final String AGGREGATE_MARKER = "__AGGREGATE__";
                int aggregateImportSuccess;
                int aggregateImportFailed;
                int aggregateGroupCount;
                boolean aggregateAnyFailure;
                String aggregateImportErrors = "";

                @Override
                protected String doInBackground() throws Exception {

                    if (scanIssues == null || webappLists == null) {
                        return "";
                    }

                    int index = webapplication_list_combox.getSelectedIndex();
                    WebAppItem selectedWebAppItem = (WebAppItem) webappLists.get(index);

                    IScanIssue issue = scanIssues[0];
                    String siteURL = parseIHTTPService(issue);

                    if (!(selectedWebAppItem.getWebAppItem_URL().trim().contains(siteURL.trim()) || siteURL.trim().contains(selectedWebAppItem.getWebAppItem_URL().trim()))) {
                        int dialogResult = JOptionPane.showConfirmDialog(frame, "WebApp URL does not match the site of which you want to import issues.\n Do you still want to proceed?",
                                "Confirm", JOptionPane.YES_NO_OPTION, JOptionPane.WARNING_MESSAGE);

                        if (dialogResult != JOptionPane.YES_OPTION) {
                            return "";
                        }
                    }
                    exportStatusLabel.setVisible(false);
                    failedExportStatusLabel.setVisible(false);
                    processing.setVisible(true);
                    String webappID = selectedWebAppItem.getWebAppItem_ID();
                    long webapp_id = Long.parseLong(webappID);

                    if (QUALYS_PORTAL_URL[portalSelectedIndex].equals(PCP)) {
                        importBurpURL = processPlatformURL(qualysPlatformURL);
                    } else {
                        importBurpURL = BurpExtender.QUALYS_PORTAL_URL[portalSelectedIndex];
                    }


                    long unixTime = System.currentTimeMillis() / 1000L;
                    String fileName = "burpextension_" + unixTime;

                    File scanreportXMLTempFile = null;
                    try {
                        scanreportXMLTempFile = File.createTempFile(fileName, ".xml");
                        scanreportXMLTempFile.deleteOnExit();
                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Making API call to send Burp issue(s) into Qualys WAS \n");
                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Temp file On Default Location: " + scanreportXMLTempFile.getAbsolutePath() + "\n");
                        logTextArea.setText(logBuilder.toString());
                    } catch (IOException e1) {
                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error creating temporary file of XML data while exporting\n");
                        logTextArea.setText(logBuilder.toString());
                    }

                    try {
                        if (scanreportXMLTempFile != null && scanreportXMLTempFile.exists()) {
                            //Added Logic to Handle Http Request Response missing from Scan Issues
                            IScanIssue[] issues = new IScanIssue[scanIssues.length];
                            int issueIndex = 0;
                            Map<String, List<String>> urlToIssueNameListMap = new HashMap<>();
                            for (IScanIssue scanIssue : scanIssues) {
                                String url = String.format("%s://%s%s", scanIssue.getUrl().getProtocol(),
                                        scanIssue.getUrl().getHost(), scanIssue.getUrl().getPath());
                                if (urlToIssueNameListMap.containsKey(url)) {
                                    urlToIssueNameListMap.get(url).add(scanIssue.getIssueName());
                                    urlToIssueNameListMap.put(url, urlToIssueNameListMap.get(url));
                                } else {
                                    List<String> issueNameList = new ArrayList<>();
                                    issueNameList.add(scanIssue.getIssueName());
                                    urlToIssueNameListMap.put(url, issueNameList);
                                }
                            }

                            for (Map.Entry<String, List<String>> entry : urlToIssueNameListMap.entrySet()) {
                                IScanIssue[] scanIssues1 = callbacks.getScanIssues(entry.getKey());
                                List<Integer> indexUsed = new ArrayList<>();
                                for (String issueName: entry.getValue()) {
                                    for (int i = 0; i < scanIssues1.length; i++) {
                                        if (scanIssues1[i].getIssueName().equals(issueName)) {
                                            if (!indexUsed.contains(i)) {
                                                indexUsed.add(i);
                                                issues[issueIndex] = scanIssues1[i];
                                                issueIndex++;
                                                break;
                                            }
                                        }
                                    }
                                }
                            }

                            logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Issues Size : " + issues.length + "\n");

                            // Trim trailing nulls (issues[] is allocated to scanIssues.length but may not be fully populated).
                            IScanIssue[] resolvedIssues = Arrays.copyOf(issues, issueIndex);

                            // Group resolved issues by host key (protocol://host). Burp's generateScanReport writes
                            // <host> elements derived from each issue's URL, so we must split when those would differ:
                            // the Qualys WAS Burp Import API (/qps/rest/3.0/import/was/burp) rejects any report whose
                            // <issue> elements reference more than one distinct <host> value with
                            // "host: Multiple hosts have been detected in report. (Multiple Hosts)."
                            LinkedHashMap<String, List<IScanIssue>> hostGroups = new LinkedHashMap<>();
                            for (IScanIssue si : resolvedIssues) {
                                if (si == null) continue;
                                String hostKey = si.getUrl().getProtocol() + "://" + si.getUrl().getHost();
                                List<IScanIssue> bucket = hostGroups.get(hostKey);
                                if (bucket == null) {
                                    bucket = new ArrayList<>();
                                    hostGroups.put(hostKey, bucket);
                                }
                                bucket.add(si);
                            }

                            // Reorder so the host matching the selected web app's URL (if any) is processed first.
                            // The first group is the one that carries purgeResults / closeUnreportedIssues semantics
                            // (see comment below); we want those flags applied against the user's intended host.
                            try {
                                String selectedUrl = selectedWebAppItem.getWebAppItem_URL();
                                if (selectedUrl != null && !selectedUrl.trim().isEmpty()) {
                                    URL wu = new URL(selectedUrl.trim());
                                    String selectedHostKey = wu.getProtocol() + "://" + wu.getHost();
                                    if (hostGroups.containsKey(selectedHostKey) && !hostGroups.keySet().iterator().next().equals(selectedHostKey)) {
                                        LinkedHashMap<String, List<IScanIssue>> reordered = new LinkedHashMap<>();
                                        reordered.put(selectedHostKey, hostGroups.get(selectedHostKey));
                                        for (Map.Entry<String, List<IScanIssue>> en : hostGroups.entrySet()) {
                                            if (!en.getKey().equals(selectedHostKey)) reordered.put(en.getKey(), en.getValue());
                                        }
                                        hostGroups = reordered;
                                    }
                                }
                            } catch (Exception ignore) { /* best-effort reordering only */ }

                            logBuilder.append(time_formatter.format(System.currentTimeMillis())
                                    + " : Issues grouped by host -> totalIssues=" + resolvedIssues.length
                                    + ", distinctHosts=" + hostGroups.size()
                                    + ", hosts=" + hostGroups.keySet() + "\n");
                            if (hostGroups.size() > 1) {
                                logBuilder.append(time_formatter.format(System.currentTimeMillis())
                                        + " : WARNING: Multiple distinct hosts detected. Qualys WAS Burp Import API"
                                        + " rejects multi-host reports; splitting into " + hostGroups.size()
                                        + " separate import calls against webAppId=" + webapp_id + ".\n");
                                logBuilder.append(time_formatter.format(System.currentTimeMillis())
                                        + " : NOTE: purgeResults/closeUnreportedIssues will be applied ONLY on the first"
                                        + " import call. Applying them on subsequent calls would undo (purge) or close"
                                        + " the findings just imported by earlier calls for the same web app.\n");
                            }
                            logTextArea.setText(logBuilder.toString());

                            int groupIndex = 0;
                            int totalSuccess = 0;
                            int totalFailed = 0;
                            boolean anyFailure = false;
                            StringBuilder errorAccumulator = new StringBuilder();

                            for (Map.Entry<String, List<IScanIssue>> grp : hostGroups.entrySet()) {
                                groupIndex++;
                                String hostKey = grp.getKey();
                                IScanIssue[] groupArr = grp.getValue().toArray(new IScanIssue[0]);

                                File groupTempFile;
                                try {
                                    groupTempFile = File.createTempFile(
                                            "burpextension_" + unixTime + "_g" + groupIndex + "_", ".xml");
                                    groupTempFile.deleteOnExit();
                                } catch (IOException ioex) {
                                    logBuilder.append(time_formatter.format(System.currentTimeMillis())
                                            + " : Failed to create temp file for host group " + groupIndex
                                            + " (host=" + hostKey + "); exception = " + ioex.getMessage() + "\n");
                                    logTextArea.setText(logBuilder.toString());
                                    anyFailure = true;
                                    totalFailed += groupArr.length;
                                    errorAccumulator.append("Group ").append(groupIndex)
                                            .append(" (host=").append(hostKey)
                                            .append("): failed to create temp file: ")
                                            .append(ioex.getMessage()).append('\n');
                                    continue;
                                }

                                callbacks.generateScanReport("xml", groupArr, groupTempFile);

                                boolean isFirstGroup = (groupIndex == 1);
                                boolean groupPurge = isFirstGroup && purgeIssues.isSelected();
                                boolean groupClose = isFirstGroup && closeIssues.isSelected();

                                logBuilder.append(time_formatter.format(System.currentTimeMillis())
                                        + " : [DEBUG] WASImport params (group " + groupIndex + "/" + hostGroups.size()
                                        + ", host=" + hostKey + ") -> "
                                        + "xmlFile=" + groupTempFile.getAbsolutePath()
                                        + ", xmlFileSizeBytes=" + groupTempFile.length()
                                        + ", issuesInGroup=" + groupArr.length
                                        + ", webappId=" + webapp_id
                                        + ", username=" + username_login
                                        + ", password=" + (password_login == null || password_login.length == 0 ? "<empty>" : "***MASKED*** (len=" + password_login.length + ")")
                                        + ", importBurpURL=" + importBurpURL
                                        + ", purgeIssues=" + groupPurge + (isFirstGroup ? "" : " (forced false; not first group)")
                                        + ", closeIssues=" + groupClose + (isFirstGroup ? "" : " (forced false; not first group)")
                                        + "\n");
                                //TODO: Uncomment below line to print debug logs while doing testing on local
                                //logTextArea.setText(logBuilder.toString());

                                wasImportRequest = new WASImport(groupTempFile, webapp_id, username_login,
                                        String.valueOf(password_login), callbacks, importBurpURL, groupPurge, groupClose);
                                String resp = wasImportRequest.sendXMLtoPortal();

                                logBuilder.append(time_formatter.format(System.currentTimeMillis())
                                        + " : Send to Qualys WAS API Response (group " + groupIndex + "/"
                                        + hostGroups.size() + ", host=" + hostKey + ") = " + resp + "\n");
                                //TODO: Uncomment below line to print debug logs while doing testing on local
                                //logTextArea.setText(logBuilder.toString());

                                if (resp != null && !resp.isEmpty() && wasImportRequest.checkExportStatus(resp)) {
                                    try { totalSuccess += wasImportRequest.parseSuccessImports(resp); } catch (Exception ignore) {}
                                    try { totalFailed += wasImportRequest.parseFailedImports(resp); } catch (Exception ignore) {}
                                } else {
                                    anyFailure = true;
                                    totalFailed += groupArr.length;
                                    errorAccumulator.append("Group ").append(groupIndex)
                                            .append(" (host=").append(hostKey).append("): ")
                                            .append(resp == null ? "<no response>" : resp).append('\n');
                                }
                            }

                            aggregateImportSuccess = totalSuccess;
                            aggregateImportFailed = totalFailed;
                            aggregateGroupCount = hostGroups.size();
                            aggregateAnyFailure = anyFailure;
                            aggregateImportErrors = errorAccumulator.toString();

                            return AGGREGATE_MARKER;
                        }
                    } catch (Exception ioe) {
                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Failed exporting data to qualys; exception = " + ioe.getMessage() + "\n");
                        logTextArea.setText(logBuilder.toString());
                    }

                    return "";
                }

                // Can safely update the GUI from this method.
                protected void done() {

                    String response;
                    try {
                        // Retrieve the return value of doInBackground.
                        response = get();

                        if (response == null || response.isEmpty()) {
                            return;
                        }

                        // Aggregated path: doInBackground() looped over per-host groups and stored counts
                        // in the worker's aggregate* fields. Surface those directly without re-parsing.
                        if (AGGREGATE_MARKER.equals(response)) {
                            processing.setVisible(false);

                            String successMsg = "";
                            String failMsg = "";

                            if (aggregateImportSuccess > 0) {
                                successMsg = "Successful import of " + aggregateImportSuccess + " issue(s) into Qualys WAS"
                                        + (aggregateGroupCount > 1 ? " across " + aggregateGroupCount + " host group(s)." : ".");
                                logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : " + successMsg + "\n");
                            }

                            if (aggregateAnyFailure || aggregateImportFailed > 0) {
                                failMsg = "Failed to import " + aggregateImportFailed + " issue(s). Please check Logs on Qualys WAS tab for details.";
                                logBuilder.append(time_formatter.format(System.currentTimeMillis())
                                        + " : Failed to import " + aggregateImportFailed
                                        + " issue(s) into Qualys WAS. Per-group error details:\n"
                                        + (aggregateImportErrors == null ? "" : aggregateImportErrors));
                            }
                            logTextArea.setText(logBuilder.toString());

                            exportStatusLabel.setText(successMsg);
                            exportStatusLabel.setForeground(Color.BLUE);
                            exportStatusLabel.setFont(new Font("Courier New", 1, 12));
                            exportStatusLabel.setVisible(true);

                            failedExportStatusLabel.setText(failMsg);
                            failedExportStatusLabel.setForeground(Color.RED);
                            failedExportStatusLabel.setFont(new Font("Courier New", 1, 12));
                            failedExportStatusLabel.setVisible(true);
                            return;
                        }

                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Send to Qualys WAS API Response = " + response + "\n");
                        logTextArea.setText(logBuilder.toString());

                        if (wasImportRequest.checkExportStatus(response)) {
                            processing.setVisible(false);

                            int success = wasImportRequest.parseSuccessImports(response);
                            int failed = wasImportRequest.parseFailedImports(response);
                            String successMsg = "";
                            String failMsg = "";
                            if (success > 0) {
                                successMsg = "Successful import of " + success + " issue(s) into Qualys WAS. ";
                                logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : " + successMsg + "\n");
                                logTextArea.setText(logBuilder.toString());
                            }

                            if (failed > 0) {
                                failMsg = "Failed to import " + failed + " issue(s). Please check Logs on Qualys WAS tab for details.";
                                logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Failed to import " + failed + " issue(s) into Qualys WAS. Please Check <errorRecords> element in the import API call response \n");
                                logTextArea.setText(logBuilder.toString());
                            }

                            exportStatusLabel.setText(successMsg);
                            exportStatusLabel.setForeground(Color.BLUE);
                            exportStatusLabel.setFont(new Font("Courier New", 1, 12));
                            exportStatusLabel.setVisible(true);

                            failedExportStatusLabel.setText(failMsg);
                            failedExportStatusLabel.setForeground(Color.RED);
                            failedExportStatusLabel.setFont(new Font("Courier New", 1, 12));
                            failedExportStatusLabel.setVisible(true);

                        } else {
                            processing.setVisible(false);
                            logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : " + response + "\n");
                            logTextArea.setText(logBuilder.toString());
                            exportStatusLabel.setText(EXPORT_XML_FILE_FAIL_ERROR_MESSAGE);
                            exportStatusLabel.setForeground(Color.red);
                            exportStatusLabel.setFont(new Font("Courier New", 1, 12));
                            exportStatusLabel.setVisible(true);
                        }


                    } catch (Exception e) {
                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Failed exporting data to qualys; exception = " + e.getMessage() + "\n");
                        logTextArea.setText(logBuilder.toString());
                    }
                }
            };

            worker.execute();
        }
    }

    private String processPlatformURL(String qualysPlatformURL) {
        String apiURL = qualysPlatformURL;
        try {
            if (qualysPlatformURL != null) {
                if (qualysPlatformURL.endsWith("/")) {
                    apiURL = qualysPlatformURL.substring(0, qualysPlatformURL.length() - 1);
                }
                return apiURL.replaceFirst("//qualysguard\\.", "//qualysapi.");
            }
        } catch (Exception e) {
            logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Exception processing qualys platform URL to API server; Exception: " + "\n");
            logTextArea.setText(logBuilder.toString());
        }
        return apiURL;
    }


    public class ImportWASDetectionListener implements ActionListener {

        @Override
        public void actionPerformed(ActionEvent e) {
            SwingWorker<String, Integer> worker = new SwingWorker<String, Integer>() {

                @Override
                protected String doInBackground() throws Exception {

                    return "";
                }

                protected void done() {
                    try {
                        if (findingIdRadio.isSelected()) {
                            if (payloadInstanceList == null) {
                                JOptionPane.showMessageDialog(frame, "Please fetch the Finding ID details first by clicking the 'Fetch' button.", "Fetch Finding Details", JOptionPane.WARNING_MESSAGE);
                                return;
                            }

                            int size = payloadInstanceList.size();
                            if (size == 1) {
                                PayloadInstance instance = payloadInstanceList.get(0);
                                sendToRepeater(instance);
                            } else if (size > 1) {
                                int index = findingIdRequestCombo.getSelectedIndex();
                                PayloadInstance instance = index == 0 ? payloadInstanceList.get(0) : payloadInstanceList.get(index - 1);
                                sendToRepeater(instance);
                            }

                        } else if (webappsRadio.isSelected()) {

                            if (findingsList == null || findingsList.size() == 0) {  // if findings are only empty
                                frame.dispose();
                                return;
                            }

                            int size = payloadInstanceForWebapps.size();
                            if (size == 1) {
                                PayloadInstance instance = payloadInstanceForWebapps.get(0);
                                sendToRepeater(instance);
                            } else if (size > 1) {
                                int index = requestPayloadCombo.getSelectedIndex();
                                PayloadInstance instance = index == 0 ? payloadInstanceForWebapps.get(0) : payloadInstanceForWebapps.get(index - 1);
                                sendToRepeater(instance);
                            }

                        }
                        frame.dispose();
                    } catch (Exception e) {
                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " Exception processing payload instances; Exception: " + e.getMessage() + "\n");
                        logTextArea.setText(logBuilder.toString());
                    }
                }

                private void sendToRepeater(PayloadInstance instance) throws Exception {
                    URL url = null;
                    url = new URL(instance.getLink());
                    boolean isHttps = url.getProtocol().equalsIgnoreCase("https");
                    int port = 80;
                    port = url.getPort() != -1 ? url.getPort() : (isHttps ? 443 : 80);

                    String firstLine = instance.getMethod() + " " + instance.getLink() + " HTTP/1.1";
                    String base64Headers = instance.getHeaders();
                    String headers = base64Headers == null || base64Headers.isEmpty() ? "" : new String(Base64.getDecoder().decode(instance.getHeaders()));
                    String base64Body = instance.getBody();
                    String body = base64Body == null || base64Body.isEmpty()  || base64Body.equalsIgnoreCase("null") ? "" : new String(Base64.getDecoder().decode(instance.getBody()));
                    String payload = "";
                    if (headers.contains("Host: ")) {
                        payload = firstLine + "\n" + headers + "\n" + body;
                    } else {
                        payload = firstLine + "\n" + "Host: " + url.getHost() + "\n" + headers + "\n" + body;
                    }

                    callbacks.sendToRepeater(url.getHost(), port, isHttps, payload.getBytes(), "WAS Request " + requestCount++);
                }
            };
            worker.execute();
        }
    }

    public class ValidateCredsActionListener implements ActionListener {
        private boolean isCredsValidationThroughWizard;

        public ValidateCredsActionListener(boolean isCredsValidationThroughWizard) {
            this.isCredsValidationThroughWizard = isCredsValidationThroughWizard;
        }

        @Override
        public void actionPerformed(ActionEvent arg0) {

            SwingWorker<String, Integer> worker = new SwingWorker<String, Integer>() {
                @Override
                protected String doInBackground() throws Exception {
                    JTextField user;
                    JPasswordField pass;
                    JComboBox<String> qualys_URI;


                    if (isCredsValidationThroughWizard) {
                        user = username_field;
                        pass = password_field;
                        qualys_URI = qualysPortal_URI_list;

                    } else {
                        user = username_field_tab;
                        pass = password_field_tab;
                        qualys_URI = qualysPortal_URI_list_tab;

                    }

                    authenticationLabel.setVisible(false);
                    authenticationLabelInTab.setVisible(false);
                    if ((user.getText() == null) || (user.getText().trim().isEmpty()) || (user.getText().trim().equals(""))) {
                        JOptionPane.showMessageDialog(upperPanel, EMPTY_LOGIN_USERNAME_INPUTFIELD_ERROR_MESSAGE, "Error Message", 0);
                    } else if ((pass.getPassword() == null) || (pass.getPassword().length == 0)) {
                        JOptionPane.showMessageDialog(upperPanel, EMPTY_LOGIN_PASSWORD_INPUTFIELD_ERROR_MESSAGE, "Error Message", 0);
                    } else {
                        if (isCredsValidationThroughWizard) {
                            processing.setVisible(true);
                        } else {
                            processingInTab.setVisible(true);
                        }
                        username_login = user.getText().trim();
                        password_login = pass.getPassword();
                        portalSelectedIndex = qualys_URI.getSelectedIndex();

                        if (qualys_URI.getSelectedIndex() != -1) {
                            String url = QUALYS_Portal_Name_List[qualys_URI.getSelectedIndex()];
                            if (url.equals(PCP)) {
                                if (isCredsValidationThroughWizard) {
                                    qualysPlatformURL = pcpURL.getText().trim();
                                } else {
                                    qualysPlatformURL = pcpURLInTab.getText().trim();
                                }
                                if (qualysPlatformURL == null || (qualysPlatformURL.trim().isEmpty())) {
                                    JOptionPane.showMessageDialog(upperPanel, EMPTY_PLATFORM_URL_INPUTFIELD_ERROR_MESSAGE, "Error Message", 0);
                                    return "";
                                }
                                searchWebappsURL = processPlatformURL(qualysPlatformURL);
                            } else {
                                searchWebappsURL = QUALYS_PORTAL_URL[qualys_URI.getSelectedIndex()];
                            }
                        }
                        wasSearchRequest = new WASSearch(searchWebappsURL, username_login, String.valueOf(password_login), callbacks);
                        return wasSearchRequest.getWebApplicationList();
                    }
                    return "";
                }

                // Can safely update the GUI from this method.
                protected void done() {

                    String response;
                    try {
                        // Retrieve the return value of doInBackground.
                        response = get();
                        if (wasSearchRequest.checkAuthenticationStatus(response)) {
                            webappLists = wasSearchRequest.parseWebApplications(response);
                            logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : " + LOGIN_SUCCESSFUL_MESSAGE + "\n");
                            logTextArea.setText(logBuilder.toString());

                            if (isCredsValidationThroughWizard) {
                                processing.setVisible(false);

                                if (INVOCATION_CONTEXT.equals("SendToQualys")) {
                                    paintNextPageInWizard(webappLists);
                                } else if (INVOCATION_CONTEXT.equals("ImportFromQualys")) {
                                    paintNextPageInWizardForImportFinding(webappLists);
                                }
                                //fill in the username and password in tab menu automatically
                                username_field_tab.setText(username_login);
                                password_field_tab.setText(String.valueOf(password_login));
                                if (qualysPlatformURL != null) {
                                    pcpURLInTab.setText(qualysPlatformURL);
                                    pcpURLInTab.setVisible(true);
                                    pcpURLLabelInTab.setVisible(true);
                                }
                                qualysPortal_URI_list_tab.setSelectedIndex(portalSelectedIndex);

                            } else {
                                processingInTab.setVisible(false);
                                authenticationLabelInTab.setText(LOGIN_SUCCESSFUL_MESSAGE);
                                authenticationLabelInTab.setVisible(true);
                                authenticationLabelInTab.setFont(new Font("Courier New", 1, 12));
                                authenticationLabelInTab.setForeground(Color.blue);
                            }
                        } else {
                            username_login = null;
                            password_login = null;

                            if (isCredsValidationThroughWizard) {
                                processing.setVisible(false);
                                authenticationLabel.setText(AUTHENTICATION_FAIL_ERROR_MESSAGE);
                                authenticationLabel.setVisible(true);
                                authenticationLabel.setFont(new Font("Courier New", 1, 12));
                                authenticationLabel.setForeground(Color.red);
                            } else {
                                processingInTab.setVisible(false);
                                authenticationLabelInTab.setText(AUTHENTICATION_FAIL_ERROR_MESSAGE);
                                authenticationLabelInTab.setVisible(true);
                                authenticationLabelInTab.setFont(new Font("Courier New", 1, 12));
                                authenticationLabelInTab.setForeground(Color.red);

                            }
                        }

                        // Update the components in Import WAS Detection flow.
                        webappsWithNone.clear();
                        webappsWithNone.add(0, "--- Select a web app ---");
                        for (int counter = 0; counter < webappLists.size(); counter++) {
                            WebAppItem webappItem = (WebAppItem) webappLists.get(counter);
                            String webappName = webappItem.getWebAppItem_Name();
                            webappsWithNone.add(webappName);
                        }
                        DefaultComboBoxModel<String> webList_model = new DefaultComboBoxModel<String>(webappsWithNone.toArray(new String[0]));
                        webappsCombo.setModel(webList_model);
                        DefaultComboBoxModel<String> empty_model = new DefaultComboBoxModel<String>();
                        findingsCombo.setModel(empty_model);
                        requestPayloadCombo.setModel(empty_model);
                        webappsPanel.repaint();

                        findingIdTextField.setText("");
                        findingIdRequestDetails.setText("");
                        findingIdRequestCombo.setModel(empty_model);
                        findingIdRequestCombo.setVisible(false);
                        findingIdRequest.setVisible(false);
                        findingIdPanel.repaint();

                        requestPayloadLabel.setVisible(false);
                        requestPayloadCombo.setVisible(false);
                        webappsFindingRequestDetails.setText("");

                        findingIdRadio.setSelected(true);
                        findingIdPanel.setVisible(true);
                        webappsPanel.setVisible(false);

                    } catch (InterruptedException e) {
                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error occurred fetching webapps; " + e.getMessage() + "\n");
                        logTextArea.setText(logBuilder.toString());
                    } catch (ExecutionException e) {
                        logBuilder.append(time_formatter.format(System.currentTimeMillis()) + " : Error occurred fetching webapps; " + e.getMessage() + "\n");
                        logTextArea.setText(logBuilder.toString());
                    }
                }

            };

            worker.execute();
        }
    }

    @Override
    public void extensionUnloaded() {
        // TODO Auto-generated method stub

    }
}
