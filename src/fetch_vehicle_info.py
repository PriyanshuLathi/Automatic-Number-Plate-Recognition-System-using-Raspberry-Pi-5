import webbrowser

class VehicleInfoFetcher:
    BASE_URL = "https://www.carinfo.app/rc-details/"

    def get_vehicle_info(self, plate_number):
        """
        Fetch vehicle information from CarInfo using license plate number
        
        Args:
            plate_number (str): License plate number to search
        
        Returns:
            bool: True if URL opened successfully, False otherwise
        """
        # Validate plate number
        if not plate_number:
            print("No plate number provided.")
            return False
        
        # Sanitize plate number (remove spaces, convert to uppercase)
        plate_number = plate_number.replace(" ", "").upper()
        
        try:
            # Construct full URL
            full_url = f"{self.BASE_URL}{plate_number}"
            
            # Open URL in default web browser
            webbrowser.open(full_url)
            
            print(f"Opened vehicle info for: {plate_number}")
            return True
        
        except Exception as e:
            print(f"Error opening vehicle info: {e}")
            return False