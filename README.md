# Youwant E-Invoice Converter

## About This Project

The **Youwant E-Invoice Converter** is a private project initially designed for **Youwant Asian Supermarket**, based in Campbelltown, Adelaide. This tool aims to provide the store owner with an efficient way to handle e-invoices from various vendors and convert them into a format compatible with the **"Enrich" POS system**. The project enhances cargo handling and inventory tracking by generating invoices in the desired Enrich format.

### Current Status

- **Supported Vendor**: Currently, the project only supports e-invoices from **KAISI** due to time constraints during development.
- **Backend**: The backend is developed in **Python**, with an integrated system for:
  - Storing **uploaded files** in an uploads folder.
  - Saving **processed files** in a dedicated processing folder.
  - Directly saving processed files to the **Desktop downloads folder** for user convenience.
- **Upload History Page**: Users can:
  - View previously uploaded files.
  - Check their upload and processing statuses.
  - Download processed files when ready.
- **Core Functionalities**:
  - **String Processing**: Handles special character removal, separation, and cleaning.
  - **Single Price Calculation**: Automatically calculates price per unit for inventory items.
  - **Column Mapping**: Ensures data columns are correctly handled and mapped.
  - **Translation**: Supports translation of item descriptions for better record-keeping.

### Current Limitations

- The project currently supports only one vendor (**KAISI**) e-invoice format.
- It has not been deployed publicly due to privacy concerns and is only available in a **local Docker environment** for development.

---

## Potential Improvements

- **Support for More Vendors**: Expand functionality to handle e-invoices from additional vendors.
- **Improved User Interface**: Introduce better alerts and layouts for enhanced user experience.
- **Additional Features**: Continue to refine and expand functionalities for a more robust application.

---

## How to Pull the Project

To download the project, pull the Docker image using the following command:

```bash
docker pull wanly129/youwantconverter:latest
```

---

##Usage Overview 
- **Upload**: Use the upload page to submit KAISI e-invoice .
- **Check Status**: Navigate to the upload history page to monitor the processing status .
- **Download**: Once processing is complete, download the converted file from the history page. 

---

##For Future Enhancements 
- Add support for more detailed logs and reports to help users understand the data processing steps.
- Provide clearer setup installations, especially for configuring the Docker environment.
- Deploy the project to a cloud or local server to make it accessible for broader usage. 

