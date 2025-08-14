import os
import asyncio

# Enable type checking in development
if os.getenv('VALIDATE') == '1':
    from type_checker import auto_validate_project
    auto_validate_project()

# Import your modules after type checker setup
import extraction_pipeline

def main():
    asyncio.run(extraction_pipeline.main())

if __name__ == "__main__":
    main()
